"""Tool registry, permissions and dispatcher with fake handlers (no database, no LLM)."""

import json
import logging

import pytest
from pydantic import BaseModel, ConfigDict, Field

from app.application.agent.dispatcher import ToolDispatcher
from app.application.agent.permissions import PERMISSIONS, Permission
from app.application.agent.registry import ToolRegistry
from app.application.agent.tool import Tool, ToolContext, ToolDataUnavailable
from app.domain.cart import InsufficientStock, InvalidQuantity, ItemNotInCart, ProductInactive
from app.domain.catalog import InvalidComparison, ProductNotFound
from app.domain.purchase import CartEmpty
from app.domain.search import SearchUnavailable

CONTEXT = ToolContext(session_id="session-1")


class PriceArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: str = Field(min_length=1, description="Product id such as MN-001")
    note: str | None = Field(default=None, description="Free text")


class NoArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LooseArgs(BaseModel):
    value: str


def make_tool(name="get_price", handler=None, args_model=PriceArgs) -> Tool:
    return Tool(
        name=name,
        description="Use for: x. Use when: y. Returns: z.",
        args_model=args_model,
        handler=handler or (lambda args, context: {"product_id": args.product_id}),
    )


def dispatcher(*tools: Tool) -> ToolDispatcher:
    return ToolDispatcher(ToolRegistry(list(tools) or [make_tool()]))


# --- permissions ---------------------------------------------------------------------------


def test_permissions_table_forbids_order_confirmation_and_cancellation():
    assert PERMISSIONS["confirm_order"] is Permission.FORBIDDEN
    assert PERMISSIONS["cancel_order"] is Permission.FORBIDDEN


def test_permissions_table_names_every_product_tool_as_free():
    free = {name for name, permission in PERMISSIONS.items() if permission is Permission.FREE}

    assert free == {
        "search_products",
        "get_product_details",
        "get_price",
        "get_stock",
        "compare_products",
        "get_alternatives",
        "view_cart",
        "add_to_cart",
        "start_checkout",
    }


# --- registry ------------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["confirm_order", "cancel_order"])
def test_registry_refuses_forbidden_tool_when_registering(name):
    with pytest.raises(ValueError, match="forbidden"):
        ToolRegistry([make_tool(name)])


def test_registry_refuses_tool_when_it_is_missing_from_permissions():
    with pytest.raises(ValueError, match="permission"):
        ToolRegistry([make_tool("delete_everything")])


def test_registry_refuses_duplicate_names():
    with pytest.raises(ValueError, match="Duplicate"):
        ToolRegistry([make_tool(), make_tool()])


def test_registry_refuses_args_model_that_allows_extra_fields():
    with pytest.raises(ValueError, match="extra"):
        ToolRegistry([make_tool(args_model=LooseArgs)])


def test_registry_exposes_names_get_and_specs_in_registration_order():
    registry = ToolRegistry([make_tool("get_stock"), make_tool("get_price")])

    assert registry.names() == ["get_stock", "get_price"]
    assert registry.get("get_price").name == "get_price"
    assert registry.get("nope") is None
    assert [spec.name for spec in registry.specs()] == ["get_stock", "get_price"]


def test_specs_are_json_schemas_that_reject_additional_properties():
    registry = ToolRegistry([make_tool(), make_tool("get_stock", args_model=NoArgs)])

    for spec in registry.specs():
        assert spec.parameters["type"] == "object"
        assert spec.parameters["additionalProperties"] is False
        json.dumps(spec.parameters)  # serializable
    assert registry.specs()[0].parameters["properties"]["product_id"]["description"]


# --- dispatcher: success -------------------------------------------------------------------


def test_dispatch_returns_handler_payload_when_arguments_are_valid():
    result = dispatcher().dispatch("get_price", {"product_id": "MN-001"}, CONTEXT)

    assert result.ok is True
    assert result.tool == "get_price"
    assert result.payload == {"product_id": "MN-001"}
    assert result.duration_ms >= 0


def test_dispatch_passes_the_session_id_from_context_to_the_handler():
    seen = []

    def handler(args, context):
        seen.append(context.session_id)
        return {}

    dispatcher(make_tool(handler=handler)).dispatch("get_price", {"product_id": "A"}, CONTEXT)

    assert seen == ["session-1"]


def test_dispatch_parses_arguments_when_they_arrive_as_a_json_object_string():
    result = dispatcher().dispatch("get_price", '{"product_id": "MN-002"}', CONTEXT)

    assert result.ok is True
    assert result.payload == {"product_id": "MN-002"}


def test_dispatch_accepts_empty_arguments_when_the_tool_takes_none():
    tool = make_tool("get_stock", handler=lambda args, context: {"ok": 1}, args_model=NoArgs)

    assert dispatcher(tool).dispatch("get_stock", {}, CONTEXT).ok is True


# --- dispatcher: argument shape ------------------------------------------------------------


@pytest.mark.parametrize("arguments", [None, "not json", "[1, 2]", "42", 7, ["a"]])
def test_dispatch_rejects_arguments_when_they_are_not_an_object(arguments):
    result = dispatcher().dispatch("get_price", arguments, CONTEXT)

    assert result.ok is False
    assert "object" in result.payload["hint"]


# --- dispatcher: permission and unknown names ----------------------------------------------


@pytest.mark.parametrize("name", ["confirm_order", "cancel_order"])
def test_dispatch_rejects_forbidden_tool_with_a_hint_about_the_interface(name):
    result = dispatcher().dispatch(name, {"order_id": "X"}, CONTEXT)

    assert result.ok is False
    assert result.payload["error"] == f"Tool {name} is not available to the assistant"
    assert "only by the user" in result.payload["hint"]


def test_dispatch_lists_available_tools_and_suggests_a_close_match_when_name_is_unknown():
    result = dispatcher(make_tool("get_price"), make_tool("get_stock")).dispatch(
        "get_prise", {}, CONTEXT
    )

    assert result.ok is False
    assert "get_prise" in result.payload["error"]
    assert "Available tools: get_price, get_stock" in result.payload["hint"]
    assert "Did you mean get_price?" in result.payload["hint"]


def test_dispatch_omits_suggestion_when_no_name_is_close():
    result = dispatcher().dispatch("zzzzzz", {}, CONTEXT)

    assert "Did you mean" not in result.payload["hint"]
    assert "Available tools: get_price" in result.payload["hint"]


def test_dispatch_treats_a_defined_but_unregistered_tool_as_unknown():
    result = dispatcher().dispatch("view_cart", {}, CONTEXT)

    assert result.ok is False
    assert "Available tools: get_price" in result.payload["hint"]


# --- dispatcher: session_id and validation -------------------------------------------------


def test_dispatch_rejects_session_id_and_never_calls_the_handler():
    calls = []
    tool = make_tool(handler=lambda args, context: calls.append(1) or {})

    result = dispatcher(tool).dispatch(
        "get_price", {"product_id": "A", "session_id": "forged"}, CONTEXT
    )

    assert result.ok is False
    assert result.payload["error"] == "session_id is set by the system"
    assert "Remove" in result.payload["hint"]
    assert calls == []


def test_dispatch_rejects_extra_fields_and_names_the_field():
    result = dispatcher().dispatch("get_price", {"product_id": "A", "colour": "red"}, CONTEXT)

    assert result.ok is False
    assert "colour" in result.payload["error"]


def test_dispatch_reports_missing_field_with_schema_in_the_hint():
    result = dispatcher().dispatch("get_price", {}, CONTEXT)

    assert result.ok is False
    assert result.payload["error"].startswith("product_id:")
    assert "Fix the arguments and call the tool again. Expected schema: {" in result.payload["hint"]
    schema = result.payload["hint"].split("Expected schema: ", 1)[1]
    assert json.loads(schema)["properties"]["product_id"]


def test_dispatch_does_not_echo_raw_values_when_validation_fails():
    result = dispatcher().dispatch("get_price", {"product_id": 12345, "note": 987654}, CONTEXT)

    assert result.ok is False
    assert "12345" not in result.payload["error"]
    assert "987654" not in result.payload["error"]


def test_dispatch_reports_at_most_three_problems():
    tool = make_tool(args_model=NoArgs)
    arguments = {"a": 1, "b": 2, "c": 3, "d": 4, "e": 5}

    result = dispatcher(tool).dispatch("get_price", arguments, CONTEXT)

    assert result.payload["error"].count(";") == 2


# --- dispatcher: handler errors ------------------------------------------------------------


def raising(error: Exception):
    def handler(args, context):
        raise error

    return handler


def run_failing(error: Exception):
    return dispatcher(make_tool(handler=raising(error))).dispatch(
        "get_price", {"product_id": "A"}, CONTEXT
    )


def test_dispatch_maps_product_not_found_to_a_hint_about_search():
    result = run_failing(ProductNotFound("MN-999"))

    assert result.ok is False
    assert "MN-999" in result.payload["error"]
    assert result.payload["hint"] == "Use search_products to find valid product ids"
    assert "retryable" not in result.payload


def test_dispatch_maps_invalid_comparison_to_a_hint_about_the_number_of_products():
    result = run_failing(InvalidComparison("Between 2 and 4 different products are needed"))

    assert result.ok is False
    assert "compare between 2 and 4 different products" in result.payload["hint"]


def test_dispatch_maps_insufficient_stock_to_the_available_units_and_a_hint():
    result = run_failing(InsufficientStock("MN-001", 9, 4))

    assert result.ok is False
    assert result.payload["error"] == "Only 4 units of MN-001 are available"
    assert result.payload["hint"] == (
        "Offer the user a smaller quantity or call get_alternatives for this product; "
        "do not add more than is available"
    )


def test_dispatch_maps_product_inactive_to_a_hint_about_other_products():
    result = run_failing(ProductInactive("MN-003"))

    assert result.ok is False
    assert "MN-003" in result.payload["error"]
    assert result.payload["hint"] == (
        "This product is not for sale; call get_alternatives or search_products to offer another"
    )


def test_dispatch_maps_invalid_quantity_to_the_allowed_range():
    result = run_failing(InvalidQuantity("Quantity must be an integer from 1 to 1000"))

    assert result.ok is False
    assert result.payload["hint"] == "quantity must be a whole number from 1 to 1000"


def test_dispatch_maps_item_not_in_cart_to_a_hint_about_view_cart():
    result = run_failing(ItemNotInCart("MN-001"))

    assert result.ok is False
    assert "MN-001" in result.payload["error"]
    assert result.payload["hint"] == "Call view_cart to see what is in the cart"


def test_dispatch_maps_cart_empty_to_a_hint_about_add_to_cart():
    result = run_failing(CartEmpty())

    assert result.ok is False
    assert result.payload["hint"] == "Add products with add_to_cart first"
    assert result.payload["error"]


def test_dispatch_marks_search_unavailable_as_retryable_and_tells_not_to_invent():
    result = run_failing(SearchUnavailable("ollama down"))

    assert result.ok is False
    assert result.payload["retryable"] is True
    assert "do not invent results" in result.payload["hint"]


def test_dispatch_maps_a_missing_data_error_to_a_hint_to_tell_the_user():
    result = run_failing(ToolDataUnavailable("The product has no price"))

    assert result.payload["error"] == "The product has no price"
    assert "not available" in result.payload["hint"]


def test_dispatch_maps_value_error_to_an_argument_fix_hint():
    result = run_failing(ValueError("The search query must not be blank"))

    assert result.payload["error"] == "The search query must not be blank"
    assert "Fix the arguments" in result.payload["hint"]


def test_dispatch_hides_unexpected_failures_and_logs_without_arguments(caplog):
    with caplog.at_level(logging.ERROR):
        result = run_failing(RuntimeError("secret internals: password=hunter2"))

    assert result.ok is False
    assert result.payload == {
        "error": "Unexpected tool failure",
        "hint": (
            "Do not retry with the same arguments; "
            "tell the user you could not complete this step"
        ),
    }
    assert caplog.records
    assert "get_price" in caplog.text
    assert "'product_id'" not in caplog.text


def test_dispatch_never_raises_when_the_handler_raises_base_exceptions_subclasses():
    for error in (KeyError("x"), ZeroDivisionError(), TypeError("bad")):
        assert run_failing(error).ok is False


# --- the result says whether the call itself was malformed (drives the loop's retry rule) ---


@pytest.mark.parametrize(
    ("name", "arguments"),
    [
        ("does_not_exist", {"product_id": "P1"}),
        ("confirm_order", {}),
        ("get_price", "not an object"),
        ("get_price", {"product_id": "P1", "session_id": "x"}),
        ("get_price", {"product_id": 5}),
        ("get_price", {}),
    ],
)
def test_result_is_marked_invalid_when_the_call_itself_is_malformed(name, arguments):
    result = dispatcher().dispatch(name, arguments, CONTEXT)

    assert result.ok is False
    assert result.invalid is True


def test_result_is_not_marked_invalid_when_the_tool_ran_fine():
    result = dispatcher().dispatch("get_price", {"product_id": "P1"}, CONTEXT)

    assert (result.ok, result.invalid) == (True, False)


def test_result_is_not_marked_invalid_when_the_tool_fails_for_a_business_reason():
    def fail(args, context):
        raise ProductNotFound("P1")

    failing = dispatcher(make_tool(handler=fail))
    result = failing.dispatch("get_price", {"product_id": "P1"}, CONTEXT)

    assert (result.ok, result.invalid) == (False, False)
