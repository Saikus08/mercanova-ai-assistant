"""Cart and checkout-preparation tools with a fake CartRepository (no database, no LLM)."""

import re
from decimal import Decimal

import pytest

from app.application.agent.cart_tools import StartCheckoutArgs, build_cart_tools
from app.application.agent.dispatcher import ToolDispatcher
from app.application.agent.permissions import PERMISSIONS, Permission
from app.application.agent.registry import ToolRegistry
from app.application.agent.tool import ToolContext
from app.domain.cart import CartLine, ProductStockInfo

CONTEXT = ToolContext(session_id="s1")
OTHER_CONTEXT = ToolContext(session_id="s2")
TOOL_NAMES = {"view_cart", "add_to_cart", "start_checkout"}
CHECKOUT_KEYS = {"ready", "cart", "problems", "next_step"}
CART_KEYS = {"items", "item_count", "total", "currency"}
LINE_KEYS = {"product_id", "name", "unit_price", "quantity", "line_total", "available_qty"}


class FakeCartRepository:
    def __init__(self) -> None:
        self.products = {
            "MN-001": ProductStockInfo("MN-001", "Vision 24", True, True, 5),
            "MN-002": ProductStockInfo("MN-002", "Office 27", True, True, 7),
            "MN-003": ProductStockInfo("MN-003", "Legacy 22", False, True, 2),
        }
        self.prices = {"MN-001": Decimal("100.00"), "MN-002": Decimal("19.99")}
        self.quantities: dict[str, dict[str, int]] = {}

    def get_lines(self, session_id: str) -> list[CartLine]:
        lines = []
        for product_id, quantity in self.quantities.get(session_id, {}).items():
            info = self.products[product_id]
            lines.append(
                CartLine(
                    product_id,
                    info.name,
                    None,
                    self.prices[product_id],
                    quantity,
                    info.available_qty,
                )
            )
        return lines

    def product_stock_info(self, product_id: str) -> ProductStockInfo | None:
        return self.products.get(product_id)

    def add_quantity(self, session_id, product_id, quantity, check) -> None:
        cart = self.quantities.setdefault(session_id, {})
        check(cart.get(product_id, 0) + quantity)
        cart[product_id] = cart.get(product_id, 0) + quantity

    def set_quantity(self, session_id, product_id, quantity, check) -> bool:
        raise NotImplementedError

    def remove_item(self, session_id, product_id) -> None:
        raise NotImplementedError

    def clear(self, session_id) -> None:
        raise NotImplementedError


@pytest.fixture
def repository() -> FakeCartRepository:
    return FakeCartRepository()


@pytest.fixture
def tools(repository):
    return build_cart_tools(repository)


@pytest.fixture
def dispatcher(tools) -> ToolDispatcher:
    return ToolDispatcher(ToolRegistry(tools))


def add(dispatcher, product_id, quantity=None, context=CONTEXT):
    arguments = {"product_id": product_id}
    if quantity is not None:
        arguments["quantity"] = quantity
    return dispatcher.dispatch("add_to_cart", arguments, context)


# --- registration --------------------------------------------------------------------------


def test_factory_builds_the_three_cart_tools(tools):
    assert {tool.name for tool in tools} == TOOL_NAMES


def test_descriptions_have_the_three_labelled_parts(tools):
    for tool in tools:
        assert re.search(r"Use for: .+ Use when: .+ Returns: .+", tool.description), tool.name


def test_every_argument_has_a_description(tools):
    for tool in tools:
        for name, prop in tool.parameters_schema().get("properties", {}).items():
            assert prop.get("description"), f"{tool.name}.{name}"


def test_tools_are_free_in_the_permission_table_and_the_registry_accepts_them(tools):
    for name in TOOL_NAMES:
        assert PERMISSIONS[name] is Permission.FREE
    assert set(ToolRegistry(tools).names()) == TOOL_NAMES


def test_start_checkout_description_states_what_it_never_does(tools):
    description = next(t for t in tools if t.name == "start_checkout").description.lower()

    assert "never creates an order" in description
    assert "never asks for personal data" in description
    assert "never confirms a purchase" in description


# --- view_cart -----------------------------------------------------------------------------


def test_view_cart_of_an_empty_cart_is_ok_and_empty(dispatcher):
    result = dispatcher.dispatch("view_cart", {}, CONTEXT)

    assert result.ok is True
    assert result.payload == {"items": [], "item_count": 0, "total": 0.0, "currency": "USD"}


def test_view_cart_format_with_money_as_rounded_floats(dispatcher):
    add(dispatcher, "MN-001", 2)
    add(dispatcher, "MN-002", 3)

    payload = dispatcher.dispatch("view_cart", {}, CONTEXT).payload

    assert set(payload) == CART_KEYS
    assert payload["items"] == [
        {
            "product_id": "MN-001",
            "name": "Vision 24",
            "unit_price": 100.0,
            "quantity": 2,
            "line_total": 200.0,
            "available_qty": 5,
        },
        {
            "product_id": "MN-002",
            "name": "Office 27",
            "unit_price": 19.99,
            "quantity": 3,
            "line_total": 59.97,
            "available_qty": 7,
        },
    ]
    assert payload["item_count"] == 5
    assert payload["total"] == 259.97
    assert payload["currency"] == "USD"


# --- add_to_cart ---------------------------------------------------------------------------


def test_add_to_cart_defaults_to_one_unit_and_returns_the_cart_and_what_was_added(dispatcher):
    result = add(dispatcher, "MN-001")

    assert result.ok is True
    assert set(result.payload) == CART_KEYS | {"added"}
    assert result.payload["added"] == {"product_id": "MN-001", "quantity": 1}
    assert result.payload["items"][0]["quantity"] == 1
    assert result.payload["total"] == 100.0


def test_add_to_cart_accumulates_quantities(dispatcher):
    add(dispatcher, "MN-001", 2)

    result = add(dispatcher, "MN-001", 3)

    assert result.payload["items"][0]["quantity"] == 5
    assert result.payload["added"] == {"product_id": "MN-001", "quantity": 3}


def test_session_id_comes_only_from_the_context(dispatcher):
    add(dispatcher, "MN-001", 2, CONTEXT)

    mine = dispatcher.dispatch("view_cart", {}, CONTEXT).payload
    other = dispatcher.dispatch("view_cart", {}, OTHER_CONTEXT).payload

    assert mine["item_count"] == 2
    assert other["items"] == []


@pytest.mark.parametrize("name", ["view_cart", "start_checkout"])
def test_session_id_in_arguments_is_rejected_without_arguments_tools(dispatcher, name):
    result = dispatcher.dispatch(name, {"session_id": "s2"}, CONTEXT)

    assert result.ok is False
    assert "session_id" in result.payload["error"]


def test_session_id_in_add_to_cart_arguments_is_rejected_and_nothing_is_added(
    dispatcher, repository
):
    result = dispatcher.dispatch(
        "add_to_cart", {"product_id": "MN-001", "session_id": "s2"}, CONTEXT
    )

    assert result.ok is False
    assert "session_id" in result.payload["error"]
    assert repository.quantities == {}


def test_add_over_stock_returns_an_actionable_error_and_leaves_the_cart_unchanged(
    dispatcher, repository
):
    add(dispatcher, "MN-001", 4)

    result = add(dispatcher, "MN-001", 2)

    assert result.ok is False
    assert result.payload["error"] == "Only 5 units of MN-001 are available"
    assert "get_alternatives" in result.payload["hint"]
    assert repository.quantities["s1"] == {"MN-001": 4}


def test_add_inactive_product_is_not_for_sale(dispatcher, repository):
    result = add(dispatcher, "MN-003", 1)

    assert result.ok is False
    assert "not for sale" in result.payload["hint"]
    assert repository.quantities == {}


def test_add_unknown_product_points_to_search(dispatcher):
    result = add(dispatcher, "NOPE", 1)

    assert result.ok is False
    assert result.payload["hint"] == "Use search_products to find valid product ids"


@pytest.mark.parametrize("quantity", [0, -1, 1001])
def test_add_invalid_quantity_is_rejected_by_the_use_case(dispatcher, repository, quantity):
    result = add(dispatcher, "MN-001", quantity)

    assert result.ok is False
    assert result.payload["hint"] == "quantity must be a whole number from 1 to 1000"
    assert repository.quantities == {}


# --- start_checkout ------------------------------------------------------------------------


def test_start_checkout_with_an_empty_cart_fails_with_the_cart_empty_hint(dispatcher):
    result = dispatcher.dispatch("start_checkout", {}, CONTEXT)

    assert result.ok is False
    assert result.payload["hint"] == "Add products with add_to_cart first"


def test_start_checkout_is_ready_when_every_line_is_covered_by_stock(dispatcher):
    add(dispatcher, "MN-001", 5)
    add(dispatcher, "MN-002", 1)

    result = dispatcher.dispatch("start_checkout", {}, CONTEXT)

    assert result.ok is True
    assert set(result.payload) == CHECKOUT_KEYS
    assert result.payload["ready"] is True
    assert result.payload["problems"] == []
    assert set(result.payload["cart"]) == CART_KEYS
    assert result.payload["cart"]["total"] == 519.99
    assert result.payload["next_step"] == (
        "Tell the user that the purchase window is ready. The user must enter their details "
        "and press the confirm button in the interface; you cannot confirm or cancel orders."
    )


def test_start_checkout_reports_every_line_that_exceeds_the_current_stock(dispatcher, repository):
    add(dispatcher, "MN-001", 5)
    add(dispatcher, "MN-002", 2)
    repository.products["MN-001"] = ProductStockInfo("MN-001", "Vision 24", True, True, 3)

    result = dispatcher.dispatch("start_checkout", {}, CONTEXT)

    assert result.ok is True
    assert result.payload["ready"] is False
    assert result.payload["problems"] == [
        {"product_id": "MN-001", "name": "Vision 24", "requested": 5, "available": 3}
    ]
    assert "adjust the quantity in the cart" in result.payload["next_step"]
    assert "confirm button" not in result.payload["next_step"]


def test_start_checkout_takes_no_arguments_and_no_personal_data(dispatcher):
    assert StartCheckoutArgs.model_fields == {}

    result = dispatcher.dispatch(
        "start_checkout", {"name": "Ana", "email": "ana@example.com", "address": "Calle 1"}, CONTEXT
    )

    assert result.ok is False
    assert "Ana" not in str(result.payload)
    assert "ana@example.com" not in str(result.payload)


def test_start_checkout_payload_never_contains_customer_fields(dispatcher):
    add(dispatcher, "MN-001", 1)

    payload = dispatcher.dispatch("start_checkout", {}, CONTEXT).payload

    assert set(payload) == CHECKOUT_KEYS
    assert set(payload["cart"]) == CART_KEYS
    assert all(set(item) == LINE_KEYS for item in payload["cart"]["items"])
    text = str(payload).lower()
    for forbidden in ("email", "address", "customer", "order_id"):
        assert forbidden not in text


def test_start_checkout_does_not_change_the_cart(dispatcher, repository):
    add(dispatcher, "MN-001", 2)
    before = {session: dict(lines) for session, lines in repository.quantities.items()}

    dispatcher.dispatch("start_checkout", {}, CONTEXT)

    assert repository.quantities == before


def test_start_checkout_description_covers_buying_what_is_already_in_the_cart():
    tools = {tool.name: tool for tool in build_cart_tools(FakeCartRepository())}

    assert "comprámelo" in tools["start_checkout"].description
    assert "use start_checkout" in tools["add_to_cart"].description
