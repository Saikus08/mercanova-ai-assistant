"""The agent loop: the model proposes tool calls, the harness checks and runs them.

One chat turn has a tool phase (the model calls tools, bounded by ``max_steps``) and a final
phase (one structured answer). Every price, stock figure and product card in the result comes
from a tool result of the same turn.
"""

import json
import logging
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from pydantic import ValidationError

from app.application.agent.answer import (
    FALLBACK_CLARIFICATION,
    FINAL_ANSWER_SCHEMA,
    MAX_RECOMMENDATIONS,
    Clarification,
    FinalAnswer,
    TurnResult,
)
from app.application.agent.dispatcher import ToolDispatcher
from app.application.agent.grounding import (
    TurnFacts,
    asks_for_negative_quantity,
    leaked_tool_names,
    numbers_in_text,
    result_cards,
    shown_products,
    too_vague_search,
    ungrounded_amounts,
    ungrounded_price_filters,
    unknown_product_ids,
)
from app.application.agent.logging_args import loggable_arguments
from app.application.agent.prompts import (
    CLARIFICATION_RETRY,
    FINAL_INSTRUCTION,
    RECOMMENDATION_RETRY,
    REJECTED_CALL_NUDGE,
    build_context,
    tool_message,
)
from app.application.agent.tool import ToolContext, ToolSpec
from app.application.ports import ChatModel
from app.domain.agent import (
    AgentState,
    ChatMessage,
    LLMUnavailable,
    ModelReply,
    Role,
    StopReason,
    ToolCall,
)

logger = logging.getLogger(__name__)

DEFAULT_TURN_TIMEOUT_SECONDS = 90.0
SEARCH_TOOL = "search_products"
ADD_TO_CART_TOOL = "add_to_cart"
GOAL_MIN_WORDS = 4
MAX_CONSECUTIVE_INVALID_CALLS = 2  # the second invalid call in a row ends the turn
MAX_FINAL_ATTEMPTS = 2  # the first answer and one retry
MAX_FINAL_CALLS = 4  # per turn: answer, validity retry, grounding retry, one completeness retry
# A turn whose successful tools are all of these needs no recommendations in the answer.
NO_RECOMMENDATION_TOOLS = {"compare_products", "get_product_details", "get_price", "get_stock"}

DEGRADED_REPLIES = {
    StopReason.LLM_UNAVAILABLE: (
        "El asistente no está disponible en este momento. Podés seguir usando el catálogo y "
        "el carrito."
    ),
    StopReason.MAX_STEPS: (
        "No pude terminar de resolver tu consulta en este turno. ¿Podés darme más detalles o "
        "reformularla?"
    ),
    StopReason.TIMEOUT: (
        "Tardé más de lo esperado en responderte. ¿Querés que lo intente de nuevo o preferís "
        "reformular la consulta?"
    ),
    StopReason.INVALID_TOOL_CALLS: (
        "No pude armar una respuesta confiable. ¿Podés reformular tu consulta?"
    ),
    StopReason.INVALID_ANSWER: (
        "No pude armar una respuesta confiable. ¿Podés reformular tu consulta?"
    ),
    StopReason.UNGROUNDED_ANSWER: (
        "No pude verificar los precios en este turno, así que prefiero no mostrarlos. "
        "¿Querés que lo intente de nuevo?"
    ),
}


class _Stop(Exception):
    """Ends the turn with a degraded answer."""

    def __init__(self, reason: StopReason) -> None:
        super().__init__(reason.value)
        self.reason = reason


@dataclass
class _Turn:
    trace_id: str
    state: AgentState
    user_texts: list[str]
    started_at: float
    facts: TurnFacts = field(default_factory=TurnFacts)
    tools_used: list[dict[str, Any]] = field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    final_calls: int = 0
    vague_blocked: bool = False
    # The last call was refused by the dispatcher and the model has not called a tool since.
    rejected_call: bool = False
    nudged: bool = False
    # Query of the last search that matched nothing: the source of the not_found block.
    empty_search_query: str | None = None
    # Cards, in order, of the last successful search: the source of the recommendation fallback.
    last_search_cards: list[dict[str, Any]] = field(default_factory=list)


class AgentLoop:
    def __init__(
        self,
        model: ChatModel,
        dispatcher: ToolDispatcher,
        tool_specs: list[ToolSpec],
        max_steps: int,
        history_messages: int,
        turn_timeout_seconds: float = DEFAULT_TURN_TIMEOUT_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._model = model
        self._dispatcher = dispatcher
        self._tool_specs = tool_specs
        self._max_steps = max_steps
        self._history_messages = history_messages
        self._turn_timeout_seconds = turn_timeout_seconds
        self._clock = clock

    def run_turn(
        self,
        state: AgentState,
        history: list[ChatMessage],
        user_message: str,
        context: ToolContext,
        on_event: Callable[[dict[str, Any]], None] | None = None,
        trace_id: str | None = None,
    ) -> TurnResult:
        user_texts = [m.content for m in history if m.role is Role.USER] + [user_message]
        turn = _Turn(trace_id or uuid.uuid4().hex, state, user_texts, self._clock())
        try:
            return self._run(turn, history, user_message, context, on_event or _ignore)
        except _Stop as stop:
            return self._degraded(turn, stop.reason)
        except LLMUnavailable:
            return self._degraded(turn, StopReason.LLM_UNAVAILABLE)
        except Exception:
            logger.exception("Agent turn failed unexpectedly trace=%s", turn.trace_id)
            raise

    # --- phases ----------------------------------------------------------------------------

    def _run(
        self,
        turn: _Turn,
        history: list[ChatMessage],
        user_message: str,
        context: ToolContext,
        on_event: Callable[[dict[str, Any]], None],
    ) -> TurnResult:
        state = turn.state
        answered_clarification = state.awaiting_clarification and bool(state.goal)
        if answered_clarification:
            # "Para jugar" alone says nothing: it completes the need that was being clarified.
            state.set_goal(f"{state.goal}. {user_message}")
        elif not state.goal:
            state.set_goal(user_message)
        state.awaiting_clarification = False
        state.step = 0
        messages = build_context(state, history, user_message, self._history_messages)

        self._tool_phase(turn, messages, context, on_event)
        # Only a turn that searched a new need (and found products) changes the goal; adding to
        # the cart, comparing or asking a price never does.
        searched_new_need = turn.last_search_cards and len(user_message.split()) >= GOAL_MIN_WORDS
        if searched_new_need and not answered_clarification:
            state.set_goal(user_message)
        messages.append(ChatMessage.user(FINAL_INSTRUCTION))
        answer = self._grounded_answer(turn, messages)
        state.awaiting_clarification = answer.clarification is not None
        return self._result(turn, answer)

    def _tool_phase(
        self,
        turn: _Turn,
        messages: list[ChatMessage],
        context: ToolContext,
        on_event: Callable[[dict[str, Any]], None],
    ) -> None:
        consecutive_invalid = 0
        for _ in range(self._max_steps):
            turn.state.step += 1
            reply = self._call(turn, messages, self._tool_specs, None, "tools")
            messages.append(ChatMessage.assistant(reply.content, reply.tool_calls))
            if not reply.tool_calls:
                if turn.rejected_call and not turn.nudged:
                    # The model answered in text instead of fixing the call it was told was
                    # wrong: one nudge, so a rejected call does not end the turn.
                    turn.nudged = True
                    messages.append(ChatMessage.user(REJECTED_CALL_NUDGE))
                    continue
                if not reply.content:
                    messages.pop()
                return
            for call in reply.tool_calls:
                valid = self._run_call(turn, call, context, on_event, messages)
                consecutive_invalid = 0 if valid else consecutive_invalid + 1
                if consecutive_invalid >= MAX_CONSECUTIVE_INVALID_CALLS:
                    raise _Stop(StopReason.INVALID_TOOL_CALLS)
        raise _Stop(StopReason.MAX_STEPS)

    @staticmethod
    def _known_ids(turn: _Turn) -> set[str]:
        """Ids a tool returned this turn or earlier turns showed to the customer."""
        return set(turn.facts.product_cards) | {p.product_id for p in turn.state.shown_products}

    def _run_call(
        self,
        turn: _Turn,
        call: ToolCall,
        context: ToolContext,
        on_event: Callable[[dict[str, Any]], None],
        messages: list[ChatMessage],
    ) -> bool:
        """Run one proposed call; return False when the call itself was invalid."""
        on_event({"type": "tool_call", "name": call.name, "arguments": call.arguments})
        turn.rejected_call = False
        invented = ungrounded_price_filters(call.arguments, turn.user_texts)
        if invented:
            ok, valid, duration_ms = False, False, 0.0
            payload: dict[str, Any] = {
                "error": f"{', '.join(invented)} was not stated by the customer",
                "hint": "Do not invent filters: ask the customer or omit it",
            }
        elif unknown_product_ids(call.arguments, self._known_ids(turn), turn.user_texts):
            ok, valid, duration_ms = False, False, 0.0
            payload = {
                "error": "The product id was not returned by any tool in this conversation",
                "hint": "Call search_products with the product name and use the product_id "
                "it returns; never guess an id",
            }
            turn.rejected_call = True
        elif call.name == ADD_TO_CART_TOOL and asks_for_negative_quantity(turn.user_texts[-1]):
            ok, valid, duration_ms = False, False, 0.0
            payload = {
                "error": "The customer asked for a negative quantity",
                "hint": "Do not add anything: tell the customer the quantity must be a whole "
                "number from 1 and ask how many units they want",
            }
        elif call.name == SEARCH_TOOL and too_vague_search(call.arguments, turn.user_texts):
            ok, valid, duration_ms = False, False, 0.0
            turn.vague_blocked = True
            payload = {
                "error": "The request is too vague to search",
                "hint": "Ask ONE clarifying question about the intended use and the budget "
                "before searching; do not recommend anything yet",
            }
        else:
            result = self._dispatcher.dispatch(call.name, call.arguments, context)
            ok, payload, duration_ms = result.ok, result.payload, result.duration_ms
            valid = not result.invalid
            turn.rejected_call = result.invalid
        turn.state.record_tool(call.name, ok)
        if ok:
            turn.facts.record(payload)
            turn.state.record_products(shown_products(payload))
            if call.name == SEARCH_TOOL:
                turn.last_search_cards = result_cards(payload)
            if call.name == SEARCH_TOOL and not payload.get("products"):
                turn.empty_search_query = str(call.arguments.get("query", "")).strip() or None
        turn.tools_used.append(
            {
                "name": call.name,
                "arguments": call.arguments,
                "ok": ok,
                "duration_ms": duration_ms,
                "result": payload,
            }
        )
        logger.info(
            "tool_call trace=%s step=%s tool=%s args=%s ok=%s duration_ms=%.0f",
            turn.trace_id,
            turn.state.step,
            call.name,
            json.dumps(loggable_arguments(call.arguments), ensure_ascii=False),
            ok,
            duration_ms,
        )
        messages.append(ChatMessage.tool(call.name, tool_message(payload)))
        return valid

    def _grounded_answer(self, turn: _Turn, messages: list[ChatMessage]) -> FinalAnswer:
        answer, raw = self._final_answer(turn, messages)
        allowed = set(turn.facts.numbers)
        for text in turn.user_texts:
            allowed |= numbers_in_text(text)
        names = [spec.name for spec in self._tool_specs]
        wrong, leaks = _problems_in(answer, allowed, names)
        if wrong or leaks:
            issues = []
            if wrong:
                amounts = ", ".join(f"{amount:.2f}" for amount in wrong)
                issues.append(
                    f"The reply mentions {amounts} but no tool returned that amount in this turn. "
                    "Rewrite using only prices returned by tools, or remove the amount."
                )
            if leaks:
                issues.append(
                    "Do not mention internal tool or function names to the customer: "
                    + ", ".join(leaks)
                )
            messages += [ChatMessage.assistant(raw), ChatMessage.user(" ".join(issues))]
            answer, raw = self._final_answer(turn, messages)
            wrong, leaks = _problems_in(answer, allowed, names)
            if wrong:
                raise _Stop(StopReason.UNGROUNDED_ANSWER)
            if leaks:
                raise _Stop(StopReason.INVALID_ANSWER)
        return self._complete(turn, messages, answer, raw, allowed, names)

    def _complete(
        self,
        turn: _Turn,
        messages: list[ChatMessage],
        answer: FinalAnswer,
        raw: str,
        allowed: set[Decimal],
        names: list[str],
    ) -> FinalAnswer:
        """At most one extra retry when the answer is valid but does not do its job."""
        if turn.vague_blocked:
            if answer.clarification:
                return answer
            instruction = CLARIFICATION_RETRY
        elif _needs_recommendations(turn, answer):
            instruction = RECOMMENDATION_RETRY
        else:
            return answer
        retried = self._retry_once(turn, messages, raw, instruction, allowed, names)
        if turn.vague_blocked:
            current = retried or answer
            if current.clarification:
                return current
            # A clarification turn never recommends.
            return current.model_copy(
                update={
                    "clarification": Clarification(**FALLBACK_CLARIFICATION),
                    "recommendations": [],
                }
            )
        return retried or answer

    def _retry_once(
        self,
        turn: _Turn,
        messages: list[ChatMessage],
        raw: str,
        instruction: str,
        allowed: set[Decimal],
        names: list[str],
    ) -> FinalAnswer | None:
        """The retried answer, or None when the cap is hit or it is invalid or ungrounded."""
        if turn.final_calls >= MAX_FINAL_CALLS:
            return None
        messages += [ChatMessage.assistant(raw), ChatMessage.user(instruction)]
        try:
            answer, _ = self._final_answer(turn, messages)
        except _Stop:
            return None
        return None if any(_problems_in(answer, allowed, names)) else answer

    def _final_answer(self, turn: _Turn, messages: list[ChatMessage]) -> tuple[FinalAnswer, str]:
        for _ in range(MAX_FINAL_ATTEMPTS):
            if turn.final_calls >= MAX_FINAL_CALLS:
                break
            turn.final_calls += 1
            reply = self._call(turn, messages, [], FINAL_ANSWER_SCHEMA, "final")
            try:
                return FinalAnswer.model_validate_json(reply.content), reply.content
            except ValidationError as error:
                messages += [
                    ChatMessage.assistant(reply.content),
                    ChatMessage.user(
                        f"Your answer was not valid: {_problems(error)}. Return valid JSON."
                    ),
                ]
        raise _Stop(StopReason.INVALID_ANSWER)

    # --- model call and results ------------------------------------------------------------

    def _call(
        self,
        turn: _Turn,
        messages: list[ChatMessage],
        tools: list[ToolSpec],
        schema: dict[str, Any] | None,
        phase: str,
    ) -> ModelReply:
        if self._clock() - turn.started_at > self._turn_timeout_seconds:
            raise _Stop(StopReason.TIMEOUT)
        started = time.perf_counter()
        try:
            reply = self._model.chat(messages, tools, schema)
        except LLMUnavailable:
            self._log_model_call(turn, phase, False, started, 0, 0)
            raise
        turn.prompt_tokens += reply.prompt_tokens
        turn.completion_tokens += reply.completion_tokens
        self._log_model_call(
            turn, phase, True, started, reply.prompt_tokens, reply.completion_tokens
        )
        return reply

    @staticmethod
    def _log_model_call(
        turn: _Turn, phase: str, ok: bool, started: float, prompt: int, completion: int
    ) -> None:
        logger.info(
            "model_call trace=%s step=%s phase=%s ok=%s duration_ms=%.0f "
            "prompt_tokens=%s completion_tokens=%s",
            turn.trace_id,
            turn.state.step,
            phase,
            ok,
            (time.perf_counter() - started) * 1000,
            prompt,
            completion,
        )

    def _result(self, turn: _Turn, answer: FinalAnswer) -> TurnResult:
        recommendations = [
            {"product": turn.facts.product_cards[item.product_id], "reason": item.reason}
            for item in answer.recommendations
            if item.product_id in turn.facts.product_cards
        ][:MAX_RECOMMENDATIONS]
        fallback_used = False
        if _needs_fallback(turn, answer, recommendations):
            recommendations = [
                {"product": product, "reason": product.get("short_description") or product["name"]}
                for product in turn.last_search_cards[:MAX_RECOMMENDATIONS]
            ]
            fallback_used = True
        returned_products = bool(recommendations) or bool(turn.facts.product_cards)
        clarification = answer.clarification.model_dump() if answer.clarification else None
        # Derived from the tool result, so the not_found block does not depend on the model
        # remembering to fill it.
        not_found = None
        if not returned_products and clarification is None:
            not_found = answer.not_found or turn.empty_search_query
        return TurnResult(
            reply=answer.reply,
            recommendations=recommendations,
            clarification=clarification,
            not_found=not_found,
            tools_used=turn.tools_used,
            steps=turn.state.step,
            stop_reason=StopReason.ANSWER,
            degraded=False,
            prompt_tokens=turn.prompt_tokens,
            completion_tokens=turn.completion_tokens,
            trace_id=turn.trace_id,
            fallback_used=fallback_used,
        )

    def _degraded(self, turn: _Turn, reason: StopReason) -> TurnResult:
        logger.warning("Agent turn degraded trace=%s reason=%s", turn.trace_id, reason.value)
        return TurnResult(
            reply=DEGRADED_REPLIES[reason],
            recommendations=[],
            clarification=None,
            not_found=None,
            tools_used=turn.tools_used,
            steps=turn.state.step,
            stop_reason=reason,
            degraded=True,
            prompt_tokens=turn.prompt_tokens,
            completion_tokens=turn.completion_tokens,
            trace_id=turn.trace_id,
        )


def _ignore(event: dict[str, Any]) -> None:
    return None


def _checked_text(answer: FinalAnswer) -> str:
    """The free text where a made-up price would reach the customer."""
    return "\n".join([answer.reply, *(item.reason for item in answer.recommendations)])


def _needs_recommendations(turn: _Turn, answer: FinalAnswer) -> bool:
    """Products came back but the answer neither recommends, asks nor reports not found."""
    if not turn.facts.product_cards:
        return False
    if answer.recommendations or answer.clarification or answer.not_found:
        return False
    return not _lookup_only(turn)


def _lookup_only(turn: _Turn) -> bool:
    used = {t["name"] for t in turn.tools_used if t["ok"]}
    return used <= NO_RECOMMENDATION_TOOLS


def _needs_fallback(
    turn: _Turn, answer: FinalAnswer, recommendations: list[dict[str, Any]]
) -> bool:
    """The model gave no usable recommendation although the last search returned products."""
    if recommendations or turn.vague_blocked or not turn.last_search_cards:
        return False
    if answer.clarification or answer.not_found:
        return False
    return not _lookup_only(turn)


def _problems_in(
    answer: FinalAnswer, allowed: set[Decimal], names: list[str]
) -> tuple[list[Decimal], list[str]]:
    text = _checked_text(answer)
    return ungrounded_amounts(text, allowed), leaked_tool_names(text, names)


def _problems(error: ValidationError) -> str:
    """Locations and messages only: the invalid input may be echoed back otherwise."""
    return "; ".join(
        f"{'.'.join(str(part) for part in item['loc']) or 'answer'}: {item['msg']}"
        for item in error.errors(include_input=False, include_url=False)
    )
