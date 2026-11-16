"""Cart tools against PostgreSQL: data is read on every call and no order is ever created."""

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.adapters.persistence.cart_repository import SqlAlchemyCartRepository
from app.adapters.persistence.orm.catalog import Brand, Category, Product
from app.adapters.persistence.orm.stock import Inventory, Price, Warehouse
from app.application.agent.cart_tools import build_cart_tools
from app.application.agent.dispatcher import ToolDispatcher
from app.application.agent.registry import ToolRegistry
from app.application.agent.tool import ToolContext

pytestmark = pytest.mark.integration

CONTEXT = ToolContext(session_id="session-a")
OTHER = ToolContext(session_id="session-b")


def product(product_id: str, name: str, **extra) -> Product:
    return Product(
        product_id=product_id,
        sku=f"SKU-{product_id}",
        name=name,
        brand_id="B1",
        subcategory_id="SC-GAM",
        category_name="Monitors",
        subcategory_name="Gaming",
        **extra,
    )


def price(product_id: str, current: str) -> Price:
    return Price(
        product_id=product_id,
        currency="USD",
        list_price=current,
        current_price=current,
        discount_percent=0,
    )


def stock(product_id: str, warehouse_id: str, qty: int) -> Inventory:
    return Inventory(
        product_id=product_id, warehouse_id=warehouse_id, on_hand_qty=qty, available_qty=qty
    )


@pytest.fixture(autouse=True)
def catalog_data(db_session: Session) -> None:
    """MN-001: 5 + 3 units in two warehouses. MN-002: 7 units. MN-003 is inactive."""
    db_session.add_all(
        [
            Brand(brand_id="B1", brand_name="Flux"),
            Category(
                subcategory_id="SC-GAM",
                subcategory_name="Gaming",
                category_id="C-MON",
                category_name="Monitors",
            ),
            Warehouse(warehouse_id="W1", warehouse_name="Centro"),
            Warehouse(warehouse_id="W2", warehouse_name="Costa"),
        ]
    )
    db_session.flush()
    db_session.add_all(
        [
            product("MN-001", "Vision 24"),
            product("MN-002", "Office 27"),
            product("MN-003", "Legacy 22", active=False),
        ]
    )
    db_session.flush()
    db_session.add_all(
        [
            price("MN-001", "100.00"),
            price("MN-002", "19.99"),
            price("MN-003", "80.00"),
            stock("MN-001", "W1", 5),
            stock("MN-001", "W2", 3),
            stock("MN-002", "W1", 7),
            stock("MN-003", "W1", 2),
        ]
    )
    db_session.flush()


@pytest.fixture
def dispatcher(db_session: Session) -> ToolDispatcher:
    return ToolDispatcher(ToolRegistry(build_cart_tools(SqlAlchemyCartRepository(db_session))))


def inventory(db_session: Session) -> list[tuple]:
    rows = db_session.execute(
        text(
            "SELECT product_id, warehouse_id, on_hand_qty, reserved_qty, available_qty "
            "FROM inventory ORDER BY 1, 2"
        )
    )
    return [tuple(row) for row in rows]


def order_count(db_session: Session) -> int:
    return db_session.execute(text("SELECT count(*) FROM orders")).scalar_one()


def add(dispatcher, product_id, quantity, context=CONTEXT):
    return dispatcher.dispatch(
        "add_to_cart", {"product_id": product_id, "quantity": quantity}, context
    )


def test_full_flow_add_view_and_start_checkout(dispatcher):
    added = add(dispatcher, "MN-001", 2)
    add(dispatcher, "MN-002", 3)

    viewed = dispatcher.dispatch("view_cart", {}, CONTEXT)
    checkout = dispatcher.dispatch("start_checkout", {}, CONTEXT)

    assert added.ok is True
    assert added.payload["added"] == {"product_id": "MN-001", "quantity": 2}
    assert viewed.payload["items"] == [
        {
            "product_id": "MN-001",
            "name": "Vision 24",
            "unit_price": 100.0,
            "quantity": 2,
            "line_total": 200.0,
            "available_qty": 8,
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
    assert viewed.payload["item_count"] == 5
    assert viewed.payload["total"] == 259.97
    assert checkout.ok is True
    assert checkout.payload["ready"] is True
    assert checkout.payload["problems"] == []
    assert checkout.payload["cart"] == viewed.payload


def test_carts_are_separated_by_the_session_of_the_context(dispatcher):
    add(dispatcher, "MN-001", 2)

    assert dispatcher.dispatch("view_cart", {}, OTHER).payload["items"] == []
    assert dispatcher.dispatch("start_checkout", {}, OTHER).ok is False


def test_adding_beyond_stock_returns_the_actionable_error_and_keeps_the_cart(dispatcher):
    add(dispatcher, "MN-001", 6)

    result = add(dispatcher, "MN-001", 3)

    assert result.ok is False
    assert result.payload["error"] == "Only 8 units of MN-001 are available"
    assert "get_alternatives" in result.payload["hint"]
    cart = dispatcher.dispatch("view_cart", {}, CONTEXT).payload
    assert [(i["product_id"], i["quantity"]) for i in cart["items"]] == [("MN-001", 6)]


def test_adding_an_inactive_product_returns_the_not_for_sale_hint(dispatcher):
    result = add(dispatcher, "MN-003", 1)

    assert result.ok is False
    assert "not for sale" in result.payload["hint"]
    assert dispatcher.dispatch("view_cart", {}, CONTEXT).payload["items"] == []


def test_start_checkout_with_an_empty_cart_fails_with_the_cart_empty_hint(dispatcher):
    result = dispatcher.dispatch("start_checkout", {}, CONTEXT)

    assert result.ok is False
    assert result.payload["hint"] == "Add products with add_to_cart first"


def test_start_checkout_reports_the_problem_when_stock_drops_below_the_cart(
    dispatcher, db_session: Session
):
    add(dispatcher, "MN-001", 6)
    db_session.execute(text("UPDATE inventory SET available_qty = 1 WHERE product_id = 'MN-001'"))

    result = dispatcher.dispatch("start_checkout", {}, CONTEXT)

    assert result.ok is True
    assert result.payload["ready"] is False
    assert result.payload["problems"] == [
        {"product_id": "MN-001", "name": "Vision 24", "requested": 6, "available": 2}
    ]
    assert "adjust the quantity in the cart" in result.payload["next_step"]


def test_view_cart_reads_the_new_price_when_the_database_changes(dispatcher, db_session: Session):
    add(dispatcher, "MN-001", 2)
    db_session.execute(text("UPDATE prices SET current_price = 80.50 WHERE product_id = 'MN-001'"))

    cart = dispatcher.dispatch("view_cart", {}, CONTEXT).payload

    assert cart["items"][0]["unit_price"] == 80.5
    assert cart["items"][0]["line_total"] == 161.0
    assert cart["total"] == 161.0


def test_the_tools_never_change_stock_and_start_checkout_creates_no_order(
    dispatcher, db_session: Session
):
    stock_before = inventory(db_session)
    orders_before = order_count(db_session)

    add(dispatcher, "MN-001", 2)
    dispatcher.dispatch("view_cart", {}, CONTEXT)
    dispatcher.dispatch("start_checkout", {}, CONTEXT)
    dispatcher.dispatch("start_checkout", {}, CONTEXT)

    assert inventory(db_session) == stock_before
    assert order_count(db_session) == orders_before
