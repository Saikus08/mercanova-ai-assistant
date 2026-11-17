"""Chat use case: conversation lifecycle around one agent turn, with in-memory fakes."""

from datetime import UTC, datetime
from typing import Any

import pytest

from app.application.agent.answer import TurnResult
from app.application.agent.tool import ToolContext
from app.application.chat import ChatService
from app.domain.agent import AgentState, ChatMessage, LLMUnavailable, Role, StopReason
from app.domain.catalog import ProductSummary
from app.domain.conversation import (
    MAX_MESSAGE_CHARS,
    ConversationNotFound,
    InvalidMessage,
    MessageRole,
    StoredMessage,
)
from tests.unit.test_chat_blocks import card, summary, turn

SESSION = "session-1"


def stored(role: MessageRole, content: str) -> StoredMessage:
    return StoredMessage(role, content, None, None, datetime(2026, 1, 1, tzinfo=UTC))


class FakeConversations:
    def __init__(self) -> None:
        self.states: dict[str, tuple[str, AgentState]] = {}
        self.messages: dict[str, list[StoredMessage]] = {}
        self.created: list[str] = []
        self.appended: list[dict[str, Any]] = []
        self.recent_limits: list[int] = []

    def create(self, session_id: str) -> str:
        conversation_id = f"conv-{len(self.created) + 1}"
        self.created.append(conversation_id)
        self.states[conversation_id] = (session_id, AgentState())
        self.messages[conversation_id] = []
        return conversation_id

    def load_state(self, conversation_id: str, session_id: str) -> AgentState:
        owner, state = self.states.get(conversation_id, (None, None))
        if owner != session_id or state is None:
            raise ConversationNotFound(conversation_id)
        return state

    def recent_messages(self, conversation_id: str, limit: int) -> list[StoredMessage]:
        self.recent_limits.append(limit)
        return self.messages[conversation_id][-limit:]

    def append_turn(
        self,
        conversation_id: str,
        user_text: str,
        assistant_text: str,
        blocks: list[dict],
        tool_calls: list[dict],
        state: AgentState,
    ) -> None:
        self.appended.append(
            {
                "conversation_id": conversation_id,
                "user_text": user_text,
                "assistant_text": assistant_text,
                "blocks": blocks,
                "tool_calls": tool_calls,
                "state": state,
            }
        )


class FakeCatalog:
    def __init__(self, summaries: list[ProductSummary]) -> None:
        self._summaries = summaries
        self.calls: list[list[str]] = []

    def get_summaries(self, product_ids: list[str]) -> list[ProductSummary]:
        self.calls.append(product_ids)
        return [s for s in self._summaries if s.product_id in product_ids]


class FakeRunner:
    def __init__(self, result: TurnResult) -> None:
        self.result = result
        self.calls: list[dict[str, Any]] = []

    def run_turn(
        self,
        state: AgentState,
        history: list[ChatMessage],
        user_message: str,
        context: ToolContext,
        on_event: Any = None,
        trace_id: str | None = None,
    ) -> TurnResult:
        self.calls.append(
            {
                "state": state,
                "history": history,
                "user_message": user_message,
                "context": context,
                "on_event": on_event,
            }
        )
        return self.result


def make_service(
    result: TurnResult | None = None, summaries: list[ProductSummary] | None = None
) -> tuple[ChatService, FakeRunner, FakeConversations, FakeCatalog]:
    runner = FakeRunner(result or turn())
    conversations = FakeConversations()
    catalog = FakeCatalog(summaries or [])
    service = ChatService(runner, conversations, catalog, history_messages=4)
    return service, runner, conversations, catalog


def recommending_turn() -> TurnResult:
    return turn(
        reply="Te recomiendo este",
        recommendations=[{"product": card("A"), "reason": "fits"}],
        tools_used=[
            {
                "name": "search_products",
                "arguments": {"query": "laptop"},
                "ok": True,
                "duration_ms": 7,
                "result": {"secret": "tool output"},
            }
        ],
        trace_id="trace-9",
    )


def test_new_conversation_creates_id_and_announces_it_before_running() -> None:
    service, runner, conversations, _ = make_service()
    order: list[str] = []
    original = runner.run_turn

    def spy(*args: Any, **kwargs: Any) -> TurnResult:
        order.append("run")
        return original(*args, **kwargs)

    runner.run_turn = spy  # type: ignore[method-assign]

    reply = service.handle(SESSION, "hola", None, on_conversation=lambda cid: order.append(cid))

    assert order == ["conv-1", "run"]
    assert reply.conversation_id == "conv-1"
    assert conversations.created == ["conv-1"]
    assert conversations.appended[0]["conversation_id"] == "conv-1"


def test_existing_conversation_passes_stored_history_without_new_message() -> None:
    service, runner, conversations, _ = make_service()
    cid = conversations.create(SESSION)
    conversations.messages[cid] = [
        stored(MessageRole.USER, "first"),
        stored(MessageRole.ASSISTANT, "answer"),
    ]

    service.handle(SESSION, "second", cid)

    assert conversations.created == [cid]
    history = runner.calls[0]["history"]
    assert history == [ChatMessage.user("first"), ChatMessage.assistant("answer")]
    assert history[0].role is Role.USER
    assert runner.calls[0]["user_message"] == "second"
    assert conversations.recent_limits == [4]


def test_unknown_or_foreign_conversation_propagates_not_found() -> None:
    service, runner, conversations, _ = make_service()
    other = conversations.create("other-session")

    with pytest.raises(ConversationNotFound):
        service.handle(SESSION, "hola", other)
    with pytest.raises(ConversationNotFound):
        service.handle(SESSION, "hola", "missing")

    assert runner.calls == []
    assert conversations.appended == []


@pytest.mark.parametrize("message", ["", "   \n\t", "x" * (MAX_MESSAGE_CHARS + 1)])
def test_invalid_message_is_rejected_before_creating_anything(message: str) -> None:
    service, runner, conversations, _ = make_service()
    announced: list[str] = []

    with pytest.raises(InvalidMessage):
        service.handle(SESSION, message, None, on_conversation=announced.append)

    assert conversations.created == []
    assert announced == []
    assert runner.calls == []


def test_message_at_the_limit_is_accepted_and_stripped() -> None:
    service, runner, _, _ = make_service()

    service.handle(SESSION, "  " + "x" * MAX_MESSAGE_CHARS + "  ", None)

    assert runner.calls[0]["user_message"] == "x" * MAX_MESSAGE_CHARS


def test_llm_unavailable_raises_and_persists_nothing() -> None:
    result = turn(stop_reason=StopReason.LLM_UNAVAILABLE, degraded=True)
    service, _, conversations, _ = make_service(result)

    with pytest.raises(LLMUnavailable):
        service.handle(SESSION, "hola", None)

    assert conversations.appended == []


def test_blocks_are_built_from_summaries_of_the_shown_products() -> None:
    service, _, conversations, catalog = make_service(
        recommending_turn(), [summary("A"), summary("Z")]
    )

    reply = service.handle(SESSION, "una laptop", None)

    assert catalog.calls == [["A"]]
    item = reply.blocks[0]["items"][0]["product"]
    assert reply.blocks[0]["type"] == "product_recommendations"
    assert item["sku"] == "SKU-A"
    assert reply.reply == "Te recomiendo este"
    assert reply.trace_id == "trace-9"
    assert reply.degraded is False
    assert conversations.appended[0]["blocks"] == reply.blocks


def test_catalog_is_not_queried_when_nothing_to_enrich() -> None:
    service, _, _, catalog = make_service(turn(reply="hola"))

    reply = service.handle(SESSION, "hola", None)

    assert catalog.calls == []
    assert reply.blocks == []


def test_persisted_tool_calls_drop_the_tool_results() -> None:
    service, _, conversations, _ = make_service(recommending_turn(), [summary("A")])

    reply = service.handle(SESSION, "una laptop", None)

    assert conversations.appended[0]["tool_calls"] == [
        {"name": "search_products", "arguments": {"query": "laptop"}, "ok": True, "duration_ms": 7}
    ]
    assert reply.tools_used == [{"name": "search_products", "args": {"query": "laptop"}}]


def test_degraded_non_llm_result_is_persisted_without_blocks() -> None:
    result = recommending_turn()
    degraded = TurnResult(
        **{**result.__dict__, "stop_reason": StopReason.MAX_STEPS, "degraded": True}
    )
    service, _, conversations, catalog = make_service(degraded, [summary("A")])

    reply = service.handle(SESSION, "una laptop", None)

    assert reply.degraded is True
    assert reply.blocks == []
    assert len(conversations.appended) == 1
    assert conversations.appended[0]["blocks"] == []
    assert conversations.appended[0]["assistant_text"] == "Te recomiendo este"
    assert catalog.calls == []


def test_on_event_and_session_id_reach_the_runner() -> None:
    service, runner, _, _ = make_service()
    events: list[dict] = []

    service.handle(SESSION, "hola", None, on_event=events.append)

    assert runner.calls[0]["on_event"] == events.append
    assert runner.calls[0]["context"] == ToolContext(SESSION)


def test_the_state_given_to_the_runner_is_the_one_saved() -> None:
    service, runner, conversations, _ = make_service()
    cid = conversations.create(SESSION)

    service.handle(SESSION, "hola", cid)

    assert conversations.appended[0]["state"] is runner.calls[0]["state"]
    assert runner.calls[0]["state"] is conversations.states[cid][1]
