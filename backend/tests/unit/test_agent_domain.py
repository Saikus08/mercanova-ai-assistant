"""Pure domain objects of the agent loop: messages and explicit conversation state."""

import dataclasses

import pytest

from app.domain.agent import (
    AgentState,
    ChatMessage,
    ModelReply,
    Role,
    ShownProduct,
    StopReason,
    ToolCall,
    ToolUse,
)


def product(product_id: str, name: str = "Name") -> ShownProduct:
    return ShownProduct(product_id, name)


def test_message_constructors_set_role_and_content():
    assert ChatMessage.system("rules") == ChatMessage(Role.SYSTEM, "rules")
    assert ChatMessage.user("hi") == ChatMessage(Role.USER, "hi")


def test_assistant_message_carries_tool_calls():
    call = ToolCall("get_price", {"product_id": "P1"})

    message = ChatMessage.assistant("", tool_calls=(call,))

    assert message.role is Role.ASSISTANT
    assert message.tool_calls == (call,)
    assert ChatMessage.assistant("done").tool_calls == ()


def test_tool_message_records_the_tool_that_produced_it():
    message = ChatMessage.tool("get_price", '{"price": 10}')

    assert message.role is Role.TOOL
    assert message.tool_name == "get_price"
    assert message.content == '{"price": 10}'
    assert ChatMessage.user("hi").tool_name is None


def test_role_and_stop_reason_values():
    assert [role.value for role in Role] == ["system", "user", "assistant", "tool"]
    assert {reason.name for reason in StopReason} == {
        "ANSWER",
        "MAX_STEPS",
        "LLM_UNAVAILABLE",
        "INVALID_TOOL_CALLS",
        "UNGROUNDED_ANSWER",
    }


def test_model_reply_defaults_token_counts_to_zero():
    reply = ModelReply("text", ())

    assert (reply.prompt_tokens, reply.completion_tokens) == (0, 0)


@pytest.mark.parametrize(
    "value",
    [
        ToolCall("a", {}),
        ChatMessage.user("x"),
        ModelReply("x", ()),
        ShownProduct("P1", "n"),
        ToolUse("a", True, 1),
    ],
)
def test_value_objects_are_frozen(value):
    with pytest.raises(dataclasses.FrozenInstanceError):
        value.name = "other"  # type: ignore[misc]


def test_record_products_keeps_the_order_in_which_they_were_shown():
    state = AgentState()

    state.record_products([product("A"), product("B")])
    state.record_products([product("C")])

    assert [p.product_id for p in state.shown_products] == ["A", "B", "C"]


def test_record_products_skips_ids_already_shown_and_keeps_their_position():
    state = AgentState()
    state.record_products([product("A"), product("B")])

    state.record_products([product("B"), product("C"), product("A"), product("C")])

    assert [p.product_id for p in state.shown_products] == ["A", "B", "C"]


def test_record_tool_appends_with_the_current_step():
    state = AgentState(step=2)

    state.record_tool("search_products", ok=True)
    state.record_tool("get_price", ok=False)

    assert state.tools_used == [
        ToolUse("search_products", True, 2),
        ToolUse("get_price", False, 2),
    ]


def test_set_goal_keeps_the_latest_non_blank_need():
    state = AgentState()

    state.set_goal("  a laptop for school  ")
    assert state.goal == "a laptop for school"

    state.set_goal("   ")
    state.set_goal("")
    assert state.goal == "a laptop for school"

    state.set_goal("a cheaper one")
    assert state.goal == "a cheaper one"


def test_set_goal_trims_to_300_characters():
    state = AgentState()

    state.set_goal("x" * 500)

    assert len(state.goal) == 300


def test_describe_for_an_empty_state():
    text = AgentState().describe()

    assert "Goal: not stated yet" in text
    assert "No products shown yet" in text
    assert "Tools used so far: none" in text
    assert "Step: 0" in text


def test_describe_for_a_filled_state_numbers_products_in_shown_order():
    state = AgentState(step=3)
    state.set_goal("a laptop for school")
    state.record_products([product("P-2", "Second"), product("P-1", "First")])
    state.record_tool("search_products", ok=True)
    state.record_tool("get_price", ok=True)

    text = state.describe()

    assert "Goal: a laptop for school" in text
    assert (
        "Products already shown to the customer, in order: 1. P-2 - Second; 2. P-1 - First" in text
    )
    assert "Tools used so far: search_products, get_price" in text
    assert "Step: 3" in text
    assert "not stated yet" not in text
    assert "No products shown yet" not in text
