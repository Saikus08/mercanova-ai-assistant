"""Chat use case: one user message in, one persisted assistant turn out."""

from collections.abc import Callable
from contextlib import AbstractContextManager, nullcontext
from dataclasses import dataclass
from typing import Any, Protocol

from app.application.agent.answer import TurnResult
from app.application.agent.tool import ToolContext
from app.application.chat_blocks import build_blocks, product_ids_to_enrich
from app.application.ports import CatalogRepository, ConversationRepository
from app.domain.agent import AgentState, ChatMessage, LLMUnavailable, StopReason
from app.domain.conversation import MAX_MESSAGE_CHARS, InvalidMessage, MessageRole


class TurnRunner(Protocol):
    def run_turn(
        self,
        state: AgentState,
        history: list[ChatMessage],
        user_message: str,
        context: ToolContext,
        on_event: Callable[[dict[str, Any]], None] | None = None,
        trace_id: str | None = None,
    ) -> TurnResult: ...


@dataclass(frozen=True)
class ChatReply:
    conversation_id: str
    reply: str
    blocks: list[dict]
    tools_used: list[dict]  # {"name", "args"}
    trace_id: str
    degraded: bool


class ChatService:
    def __init__(
        self,
        runner: TurnRunner,
        conversations: ConversationRepository,
        catalog: CatalogRepository,
        history_messages: int,
    ) -> None:
        self._runner = runner
        self._conversations = conversations
        self._catalog = catalog
        self._history_messages = history_messages

    def handle(
        self,
        session_id: str,
        message: str,
        conversation_id: str | None,
        on_event: Callable[[dict], None] | None = None,
        on_conversation: Callable[[str], None] | None = None,
    ) -> ChatReply:
        text = message.strip()
        if not text or len(text) > MAX_MESSAGE_CHARS:
            raise InvalidMessage(f"Message must have 1 to {MAX_MESSAGE_CHARS} characters")

        # A new conversation has nobody to compete with; an existing one is held for the whole
        # turn, from reading its state to saving it.
        lock: AbstractContextManager[None] = (
            nullcontext()
            if conversation_id is None
            else self._conversations.turn_lock(conversation_id)
        )
        with lock:
            return self._turn(session_id, text, conversation_id, on_event, on_conversation)

    def _turn(
        self,
        session_id: str,
        text: str,
        conversation_id: str | None,
        on_event: Callable[[dict], None] | None,
        on_conversation: Callable[[str], None] | None,
    ) -> ChatReply:
        if conversation_id is not None:
            state = self._conversations.load_state(conversation_id, session_id)
        else:
            conversation_id = self._conversations.create(session_id)
            state = AgentState()
        if on_conversation is not None:
            on_conversation(conversation_id)

        history = [
            ChatMessage.user(m.content)
            if m.role is MessageRole.USER
            else ChatMessage.assistant(m.content)
            for m in self._conversations.recent_messages(conversation_id, self._history_messages)
        ]
        result = self._runner.run_turn(state, history, text, ToolContext(session_id), on_event)
        if result.stop_reason is StopReason.LLM_UNAVAILABLE:
            raise LLMUnavailable("The model is unavailable")

        ids = [] if result.degraded else product_ids_to_enrich(result)
        summaries = {s.product_id: s for s in self._catalog.get_summaries(ids)} if ids else {}
        blocks = build_blocks(result, summaries)
        tool_calls = [
            {
                "name": use["name"],
                "arguments": use["arguments"],
                "ok": use["ok"],
                "duration_ms": use["duration_ms"],
            }
            for use in result.tools_used
        ]
        self._conversations.append_turn(
            conversation_id, text, result.reply, blocks, tool_calls, state
        )
        return ChatReply(
            conversation_id=conversation_id,
            reply=result.reply,
            blocks=blocks,
            tools_used=[{"name": u["name"], "args": u["arguments"]} for u in result.tools_used],
            trace_id=result.trace_id,
            degraded=result.degraded,
        )
