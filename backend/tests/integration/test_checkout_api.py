"""Checkout, confirmation and cancellation against PostgreSQL with a small hand-made catalog."""

import logging
import re
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import StatementError
from sqlalchemy.orm import Session

from app.adapters.persistence.order_repository import SqlAlchemyOrderRepository
from app.adapters.persistence.orm.catalog import Brand, Category, Product
from app.adapters.persistence.orm.stock import Inventory, Price, Warehouse

pytestmark = pytest.mark.integration

HEADERS = {"X-Session-Id": "session-a"}
OTHER = {"X-Session-Id": "session-b"}
CUSTOMER = {"name": "Ana Pérez", "email": "ana@example.com", "address": "Av. 18 de Julio 1234"}
PICKUP_W1 = {"method": "pickup", "warehouse_id": "W1"}
SHIPPING = {"method": "shipping"}
TODAY = datetime.now(UTC).strftime("%Y%m%d")


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


def stock(product_id: str, warehouse_id: str, qty: int, reserved: int = 0) -> Inventory:
    return Inventory(
        product_id=product_id,
        warehouse_id=warehouse_id,
        on_hand_qty=qty + reserved,
        reserved_qty=reserved,
        available_qty=qty,
    )


@pytest.fixture(autouse=True)
def catalog_data(db_session: Session) -> None:
    """MN-001: W1 5, W2 3, W3 4 (W3 pickup only). MN-002: W1 7 (+2 reserved). MN-003 inactive."""
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
            Warehouse(warehouse_id="W3", warehouse_name="Retiro", shipping_enabled=False),
            Warehouse(warehouse_id="W4", warehouse_name="Cerrado", pickup_enabled=False),
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
            stock("MN-001", "W3", 4),
            stock("MN-002", "W1", 7, reserved=2),
            stock("MN-003", "W1", 2),
        ]
    )
    # Committed so a rollback inside the code under test keeps the catalog.
    db_session.commit()


def sql(db_session: Session, statement: str) -> None:
    db_session.execute(text(statement))
    db_session.commit()


def add(client: TestClient, product_id: str, quantity: int, headers=HEADERS) -> None:
    response = client.post(
        "/api/cart/items", json={"product_id": product_id, "quantity": quantity}, headers=headers
    )
    assert response.status_code == 200, response.text


def post_checkout(client: TestClient, customer=CUSTOMER, delivery=PICKUP_W1, headers=HEADERS):
    return client.post(
        "/api/checkout", json={"customer": customer, "delivery": delivery}, headers=headers
    )


def make_order(client: TestClient, delivery=PICKUP_W1, headers=HEADERS) -> dict:
    response = post_checkout(client, delivery=delivery, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def confirm(client: TestClient, order_id: str, headers=HEADERS):
    return client.post(f"/api/orders/{order_id}/confirm", headers=headers)


def cancel(client: TestClient, order_id: str, headers=HEADERS):
    return client.post(f"/api/orders/{order_id}/cancel", headers=headers)


def inventory(db_session: Session) -> list[tuple]:
    rows = db_session.execute(
        text(
            "SELECT product_id, warehouse_id, on_hand_qty, reserved_qty, available_qty "
            "FROM inventory ORDER BY 1, 2"
        )
    )
    return [tuple(row) for row in rows]


def cart_quantities(client: TestClient, headers=HEADERS) -> dict[str, int]:
    items = client.get("/api/cart", headers=headers).json()["items"]
    return {i["product_id"]: i["quantity"] for i in items}


def order_status(db_session: Session, order_id: str) -> str:
    return db_session.execute(
        text("SELECT status FROM orders WHERE order_id = :id"), {"id": order_id}
    ).scalar_one()


def allocations(db_session: Session) -> list[tuple]:
    rows = db_session.execute(
        text(
            "SELECT order_id, product_id, warehouse_id, quantity "
            "FROM order_allocations ORDER BY 1, 2, 3"
        )
    )
    return [tuple(row) for row in rows]


def assert_available_is_on_hand_minus_reserved(db_session: Session) -> None:
    for _, _, on_hand, reserved, available in inventory(db_session):
        assert available == on_hand - reserved


# --- checkout ---


def test_checkout_creates_a_pending_order_with_current_prices(
    client: TestClient, db_session: Session
):
    add(client, "MN-001", 2)
    add(client, "MN-002", 1)
    before = inventory(db_session)

    response = post_checkout(client)

    assert response.status_code == 201
    body = response.json()
    assert re.fullmatch(rf"ORD-{TODAY}-\d{{4}}", body["order_id"])
    created_at = body.pop("created_at")
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", created_at)
    assert body == {
        "order_id": body["order_id"],
        "status": "pending_confirmation",
        "confirmed_at": None,
        "customer": CUSTOMER,
        "delivery": {"method": "pickup", "warehouse_id": "W1"},
        "items": [
            {
                "product_id": "MN-001",
                "name": "Vision 24",
                "unit_price": 100.0,
                "quantity": 2,
                "line_total": 200.0,
            },
            {
                "product_id": "MN-002",
                "name": "Office 27",
                "unit_price": 19.99,
                "quantity": 1,
                "line_total": 19.99,
            },
        ],
        "total": 219.99,
        "currency": "USD",
    }
    assert inventory(db_session) == before
    assert cart_quantities(client) == {"MN-001": 2, "MN-002": 1}
    assert allocations(db_session) == []


def test_checkout_trims_customer_and_ignores_warehouse_for_shipping(client: TestClient):
    add(client, "MN-001", 1)
    customer = {"name": "  Ana  ", "email": " ana@example.com ", "address": " Calle 1 "}
    body = post_checkout(client, customer, {"method": "shipping", "warehouse_id": "W1"}).json()
    assert body["customer"] == {"name": "Ana", "email": "ana@example.com", "address": "Calle 1"}
    assert body["delivery"] == {"method": "shipping", "warehouse_id": None}


def test_order_ids_count_up_within_the_day(client: TestClient):
    add(client, "MN-001", 1)
    first = make_order(client)["order_id"]
    second = make_order(client)["order_id"]
    assert (first, second) == (f"ORD-{TODAY}-0001", f"ORD-{TODAY}-0002")


def test_checkout_with_empty_cart(client: TestClient):
    response = post_checkout(client)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CART_EMPTY"
    assert response.json()["error"]["message"] == "El carrito está vacío."


def test_checkout_rejects_inactive_product(client: TestClient, db_session: Session):
    add(client, "MN-001", 1)
    sql(db_session, "UPDATE products SET active = false WHERE product_id = 'MN-001'")
    response = post_checkout(client)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "PRODUCT_INACTIVE"


def test_checkout_insufficient_stock_for_pickup(client: TestClient, db_session: Session):
    add(client, "MN-001", 5)
    sql(
        db_session,
        "UPDATE inventory SET available_qty = 2 "
        "WHERE product_id = 'MN-001' AND warehouse_id = 'W1'",
    )
    response = post_checkout(client)
    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "INSUFFICIENT_STOCK"
    assert error["details"] == {"product_id": "MN-001", "available_qty": 2}
    assert db_session.execute(text("SELECT count(*) FROM orders")).scalar_one() == 0


def test_checkout_insufficient_stock_for_shipping_counts_shipping_warehouses_only(
    client: TestClient, db_session: Session
):
    add(client, "MN-001", 8)  # W1 5 + W2 3 ship, W3 4 does not
    assert post_checkout(client, delivery=SHIPPING).status_code == 201
    sql(
        db_session,
        "UPDATE inventory SET available_qty = 2 "
        "WHERE product_id = 'MN-001' AND warehouse_id = 'W2'",
    )
    error = post_checkout(client, delivery=SHIPPING).json()["error"]
    assert error["details"] == {"product_id": "MN-001", "available_qty": 7}


@pytest.mark.parametrize(
    "customer",
    [
        {"name": "  ", "email": "ana@example.com", "address": "Calle 1"},
        {"name": "Ana", "email": "ana-at-example", "address": "Calle 1"},
        {"name": "Ana", "email": "ana@example.com", "address": ""},
        {"name": "Ana", "email": "ana@example.com"},
        {"name": "A" * 121, "email": "ana@example.com", "address": "Calle 1"},
    ],
)
def test_invalid_customer_is_a_validation_error(client: TestClient, customer):
    add(client, "MN-001", 1)
    response = post_checkout(client, customer)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert response.json()["error"]["details"]["errors"]


@pytest.mark.parametrize(
    "delivery",
    [
        {"method": "pickup"},
        {"method": "pickup", "warehouse_id": "NOPE"},
        {"method": "pickup", "warehouse_id": "W4"},
        {"method": "drone"},
    ],
)
def test_invalid_delivery_is_a_validation_error(client: TestClient, delivery):
    add(client, "MN-001", 1)
    response = post_checkout(client, delivery=delivery)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_validation_errors_do_not_echo_personal_data(client: TestClient):
    add(client, "MN-001", 1)
    customer = {
        "name": "Zoe Quillfeather",
        "email": "zoe-secret-mail",
        "address": "Calle Secreta 99",
    }
    cases = [
        post_checkout(client, customer),
        post_checkout(client, {**customer, "email": "zoe@secret.test", "name": 7}),
        post_checkout(client, {**customer, "email": "zoe@secret.test"}, {"method": "pickup"}),
    ]
    for response in cases:
        assert response.status_code == 400
        for secret in ("Quillfeather", "zoe", "Secreta"):
            assert secret not in response.text


def test_checkout_requires_a_session(client: TestClient):
    response = client.post("/api/checkout", json={"customer": CUSTOMER, "delivery": PICKUP_W1})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "MISSING_SESSION"


def test_unexpected_failure_does_not_log_personal_data(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
):
    add(client, "MN-001", 1)
    customer = {
        "name": "Zoe Quillfeather",
        "email": "zoe.q@secret.test",
        "address": "Calle Secreta 99",
    }

    def fail(*args, **kwargs):
        raise StatementError("insert failed", "INSERT INTO orders ...", dict(customer), None)

    monkeypatch.setattr(SqlAlchemyOrderRepository, "_next_order_number", fail)
    with caplog.at_level(logging.DEBUG):
        response = post_checkout(client, customer)

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert caplog.records, "the failure must still be logged"
    for secret in ("Quillfeather", "zoe.q", "Secreta"):
        assert secret not in caplog.text
        assert secret not in response.text


# --- confirm ---


def test_confirm_decrements_stock_records_allocations_and_empties_the_cart(
    client: TestClient, db_session: Session
):
    add(client, "MN-001", 2)
    add(client, "MN-002", 1)
    add(client, "MN-001", 1, headers=OTHER)
    order = make_order(client)

    response = confirm(client, order["order_id"])

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "confirmed"
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", body["confirmed_at"])
    assert {k: body[k] for k in ("order_id", "items", "total", "customer", "delivery")} == {
        k: order[k] for k in ("order_id", "items", "total", "customer", "delivery")
    }
    assert inventory(db_session) == [
        ("MN-001", "W1", 3, 0, 3),
        ("MN-001", "W2", 3, 0, 3),
        ("MN-001", "W3", 4, 0, 4),
        ("MN-002", "W1", 8, 2, 6),
        ("MN-003", "W1", 2, 0, 2),
    ]
    assert_available_is_on_hand_minus_reserved(db_session)
    assert allocations(db_session) == [
        (order["order_id"], "MN-001", "W1", 2),
        (order["order_id"], "MN-002", "W1", 1),
    ]
    assert cart_quantities(client) == {}
    assert cart_quantities(client, OTHER) == {"MN-001": 1}


def test_confirm_twice_is_rejected(client: TestClient, db_session: Session):
    add(client, "MN-001", 1)
    order_id = make_order(client)["order_id"]
    assert confirm(client, order_id).status_code == 200
    after_first = inventory(db_session)

    response = confirm(client, order_id)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ORDER_NOT_PENDING"
    assert response.json()["error"]["message"] == "La orden ya fue confirmada o cancelada."
    assert inventory(db_session) == after_first


def test_confirm_another_sessions_order_is_not_found(client: TestClient, db_session: Session):
    add(client, "MN-001", 1)
    order_id = make_order(client)["order_id"]
    before = inventory(db_session)

    response = confirm(client, order_id, headers=OTHER)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ORDER_NOT_FOUND"
    assert response.json()["error"]["message"] == "La orden no existe."
    assert order_status(db_session, order_id) == "pending_confirmation"
    assert inventory(db_session) == before


def test_confirm_and_cancel_unknown_order(client: TestClient):
    for call in (confirm, cancel):
        response = call(client, "ORD-19990101-0001")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "ORDER_NOT_FOUND"


def test_confirm_requires_a_session(client: TestClient):
    response = client.post("/api/orders/ORD-1/confirm")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "MISSING_SESSION"


def test_confirm_with_changed_price_keeps_everything_untouched(
    client: TestClient, db_session: Session
):
    add(client, "MN-001", 2)
    order_id = make_order(client)["order_id"]
    before = inventory(db_session)
    sql(db_session, "UPDATE prices SET current_price = 120.50 WHERE product_id = 'MN-001'")

    response = confirm(client, order_id)

    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "PRICE_CHANGED"
    assert error["message"] == "El precio cambió desde que armaste la orden."
    assert error["details"] == {"product_id": "MN-001", "old_price": 100.0, "new_price": 120.5}
    assert order_status(db_session, order_id) == "pending_confirmation"
    assert inventory(db_session) == before
    assert allocations(db_session) == []
    assert cart_quantities(client) == {"MN-001": 2}


def test_confirm_with_stock_lowered_after_checkout_changes_nothing(
    client: TestClient, db_session: Session
):
    add(client, "MN-001", 4)
    order_id = make_order(client)["order_id"]
    sql(
        db_session,
        "UPDATE inventory SET available_qty = 1 "
        "WHERE product_id = 'MN-001' AND warehouse_id = 'W1'",
    )
    before = inventory(db_session)

    response = confirm(client, order_id)

    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "INSUFFICIENT_STOCK"
    assert error["details"] == {"product_id": "MN-001", "available_qty": 1}
    assert order_status(db_session, order_id) == "pending_confirmation"
    assert inventory(db_session) == before
    assert cart_quantities(client) == {"MN-001": 4}


def test_confirm_is_atomic_when_the_second_product_lacks_stock(
    client: TestClient, db_session: Session
):
    add(client, "MN-001", 2)
    add(client, "MN-002", 3)
    order_id = make_order(client)["order_id"]
    sql(db_session, "UPDATE inventory SET available_qty = 1 WHERE product_id = 'MN-002'")
    before = inventory(db_session)

    response = confirm(client, order_id)

    assert response.status_code == 409
    assert response.json()["error"]["details"]["product_id"] == "MN-002"
    assert inventory(db_session) == before  # MN-001 was not decremented
    assert allocations(db_session) == []


def test_confirm_rolls_back_a_failure_after_part_of_the_stock_was_taken(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
):
    add(client, "MN-001", 2)
    add(client, "MN-002", 1)
    order_id = make_order(client)["order_id"]
    before = inventory(db_session)
    original = SqlAlchemyOrderRepository._allocate
    calls = []

    def fail_on_second(self, order_id, allocation):
        calls.append(allocation)
        if len(calls) == 2:
            raise RuntimeError("disk on fire")
        original(self, order_id, allocation)

    monkeypatch.setattr(SqlAlchemyOrderRepository, "_allocate", fail_on_second)

    response = confirm(client, order_id)

    assert response.status_code == 500
    assert len(calls) == 2
    assert order_status(db_session, order_id) == "pending_confirmation"
    assert inventory(db_session) == before
    assert allocations(db_session) == []
    assert cart_quantities(client) == {"MN-001": 2, "MN-002": 1}


def test_shipping_takes_from_the_warehouse_with_most_stock_then_the_next(
    client: TestClient, db_session: Session
):
    add(client, "MN-001", 6)
    order = make_order(client, delivery=SHIPPING)

    assert confirm(client, order["order_id"]).status_code == 200

    assert [r for r in inventory(db_session) if r[0] == "MN-001"] == [
        ("MN-001", "W1", 0, 0, 0),
        ("MN-001", "W2", 2, 0, 2),
        ("MN-001", "W3", 4, 0, 4),
    ]
    assert allocations(db_session) == [
        (order["order_id"], "MN-001", "W1", 5),
        (order["order_id"], "MN-001", "W2", 1),
    ]
    assert_available_is_on_hand_minus_reserved(db_session)


def test_pickup_uses_only_the_chosen_warehouse(client: TestClient, db_session: Session):
    add(client, "MN-001", 3)
    order = make_order(client, delivery={"method": "pickup", "warehouse_id": "W2"})

    assert confirm(client, order["order_id"]).status_code == 200

    assert [r for r in inventory(db_session) if r[0] == "MN-001"] == [
        ("MN-001", "W1", 5, 0, 5),
        ("MN-001", "W2", 0, 0, 0),
        ("MN-001", "W3", 4, 0, 4),
    ]
    assert allocations(db_session) == [(order["order_id"], "MN-001", "W2", 3)]


# --- cancel ---


def test_cancel_a_pending_order_leaves_stock_and_blocks_confirmation(
    client: TestClient, db_session: Session
):
    add(client, "MN-001", 2)
    order_id = make_order(client)["order_id"]
    before = inventory(db_session)

    response = cancel(client, order_id)

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    assert response.json()["confirmed_at"] is None
    assert inventory(db_session) == before
    assert order_status(db_session, order_id) == "cancelled"
    assert db_session.execute(
        text("SELECT cancelled_at IS NOT NULL FROM orders WHERE order_id = :id"), {"id": order_id}
    ).scalar_one()
    assert cart_quantities(client) == {"MN-001": 2}
    again = confirm(client, order_id)
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "ORDER_NOT_PENDING"
    assert cancel(client, order_id).json()["error"]["code"] == "ORDER_NOT_PENDING"


def test_cancel_another_sessions_order_is_not_found(client: TestClient, db_session: Session):
    add(client, "MN-001", 1)
    order_id = make_order(client)["order_id"]
    assert cancel(client, order_id, headers=OTHER).status_code == 404
    assert order_status(db_session, order_id) == "pending_confirmation"


def test_confirmed_order_cannot_be_cancelled(client: TestClient, db_session: Session):
    add(client, "MN-001", 1)
    order_id = make_order(client)["order_id"]
    confirm(client, order_id)
    response = cancel(client, order_id)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ORDER_NOT_PENDING"
    assert order_status(db_session, order_id) == "confirmed"


# --- history (RF-16) ---


def list_orders(client: TestClient, headers=HEADERS):
    return client.get("/api/orders", headers=headers)


def get_order(client: TestClient, order_id: str, headers=HEADERS):
    return client.get(f"/api/orders/{order_id}", headers=headers)


def test_history_is_empty_for_a_new_session(client: TestClient):
    response = list_orders(client)
    assert response.status_code == 200
    assert response.json() == []


def test_history_lists_the_sessions_orders_newest_first_in_every_status(client: TestClient):
    add(client, "MN-001", 1)
    first = make_order(client)
    second = make_order(client)
    third = make_order(client)
    confirm(client, first["order_id"])
    cancel(client, second["order_id"])
    add(client, "MN-002", 1, headers=OTHER)
    make_order(client, headers=OTHER)

    response = list_orders(client)

    assert response.status_code == 200
    body = response.json()
    assert [(o["order_id"], o["status"]) for o in body] == [
        (third["order_id"], "pending_confirmation"),
        (second["order_id"], "cancelled"),
        (first["order_id"], "confirmed"),
    ]
    assert body[2]["confirmed_at"] is not None
    assert body[1]["confirmed_at"] is None
    assert body[2]["items"] == first["items"]


def test_history_shows_the_price_paid_even_if_the_price_changes_later(
    client: TestClient, db_session: Session
):
    add(client, "MN-001", 2)
    order_id = make_order(client)["order_id"]
    confirm(client, order_id)
    sql(db_session, "UPDATE prices SET current_price = 150.00 WHERE product_id = 'MN-001'")
    sql(db_session, "UPDATE products SET name = 'Vision 24 v2' WHERE product_id = 'MN-001'")

    (order,) = list_orders(client).json()

    assert order["items"] == [
        {
            "product_id": "MN-001",
            "name": "Vision 24",
            "unit_price": 100.0,
            "quantity": 2,
            "line_total": 200.0,
        }
    ]
    assert order["total"] == 200.0
    assert get_order(client, order_id).json() == order


def test_get_order_returns_the_same_body_as_checkout(client: TestClient):
    add(client, "MN-001", 2)
    add(client, "MN-002", 1)
    created = make_order(client)

    response = get_order(client, created["order_id"])

    assert response.status_code == 200
    assert response.json() == created


def test_get_order_of_another_session_or_unknown_is_not_found(client: TestClient):
    add(client, "MN-001", 1)
    order_id = make_order(client)["order_id"]
    for response in (get_order(client, order_id, OTHER), get_order(client, "ORD-19990101-0001")):
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "ORDER_NOT_FOUND"


def test_history_requires_a_session(client: TestClient):
    for response in (client.get("/api/orders"), client.get("/api/orders/ORD-1")):
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "MISSING_SESSION"
