"""SqlAlchemyConversationRepository against PostgreSQL."""

import pytest
from sqlalchemy.orm import Session

from app.adapters.persistence.conversation_repository import SqlAlchemyConversationRepository
from app.domain.agent import AgentState, ShownProduct
from app.domain.conversation import ConversationNotFound, MessageRole

pytestmark = pytest.mark.integration

SESSION = "session-a"
OTHER = "session-b"


@pytest.fixture
def repo(db_session: Session) -> SqlAlchemyConversationRepository:
    return SqlAlchemyConversationRepository(db_session)


def add_turn(repo, conversation_id: str, n: int, **extra) -> None:
    repo.append_turn(
        conversation_id,
        f"question {n}",
        f"answer {n}",
        extra.get("blocks", []),
        extra.get("tool_calls", []),
        extra.get("state", AgentState()),
    )


def test_create_returns_id_with_default_state(repo) -> None:
    conversation_id = repo.create(SESSION)

    state = repo.load_state(conversation_id, SESSION)

    assert state.to_dict() == AgentState().to_dict()


def test_state_round_trips_through_append_turn(repo) -> None:
    conversation_id = repo.create(SESSION)
    state = AgentState()
    state.set_goal("a quiet monitor")
    state.step = 2
    state.record_products([ShownProduct("MN-001", "Flux 27")])
    state.record_tool("search_products", True)

    add_turn(repo, conversation_id, 1, state=state)

    assert repo.load_state(conversation_id, SESSION).to_dict() == state.to_dict()


def test_messages_keep_user_before_assistant_across_turns(repo) -> None:
    conversation_id = repo.create(SESSION)
    add_turn(repo, conversation_id, 1)
    add_turn(repo, conversation_id, 2)

    messages = repo.list_messages(conversation_id, SESSION)

    assert [(m.role, m.content) for m in messages] == [
        (MessageRole.USER, "question 1"),
        (MessageRole.ASSISTANT, "answer 1"),
        (MessageRole.USER, "question 2"),
        (MessageRole.ASSISTANT, "answer 2"),
    ]


def test_recent_messages_returns_the_last_ones_oldest_first(repo) -> None:
    conversation_id = repo.create(SESSION)
    for n in (1, 2, 3):
        add_turn(repo, conversation_id, n)

    messages = repo.recent_messages(conversation_id, 3)

    assert [m.content for m in messages] == ["answer 2", "question 3", "answer 3"]


def test_recent_messages_of_empty_conversation(repo) -> None:
    assert repo.recent_messages(repo.create(SESSION), 5) == []


@pytest.mark.parametrize("conversation_id", ["00000000-0000-4000-8000-000000000000", "not-a-uuid"])
def test_unknown_or_malformed_id_is_not_found(repo, conversation_id: str) -> None:
    with pytest.raises(ConversationNotFound):
        repo.load_state(conversation_id, SESSION)
    with pytest.raises(ConversationNotFound):
        repo.list_messages(conversation_id, SESSION)


def test_other_session_cannot_read_the_conversation(repo) -> None:
    conversation_id = repo.create(SESSION)
    add_turn(repo, conversation_id, 1)

    with pytest.raises(ConversationNotFound):
        repo.load_state(conversation_id, OTHER)
    with pytest.raises(ConversationNotFound):
        repo.list_messages(conversation_id, OTHER)


def test_list_messages_is_scoped_to_the_conversation(repo) -> None:
    first = repo.create(SESSION)
    second = repo.create(SESSION)
    add_turn(repo, first, 1)
    add_turn(repo, second, 2)

    assert [m.content for m in repo.list_messages(first, SESSION)] == ["question 1", "answer 1"]


def test_blocks_and_tool_calls_are_stored_on_the_assistant_message(repo) -> None:
    conversation_id = repo.create(SESSION)
    blocks = [{"type": "product_cards", "products": [{"product_id": "MN-001"}]}]
    tool_calls = [{"name": "search_products", "arguments": {"query": "monitor"}, "ok": True}]

    add_turn(repo, conversation_id, 1, blocks=blocks, tool_calls=tool_calls)

    user, assistant = repo.list_messages(conversation_id, SESSION)
    assert (user.blocks, user.tool_calls) == (None, None)
    assert assistant.blocks == blocks
    assert assistant.tool_calls == tool_calls
