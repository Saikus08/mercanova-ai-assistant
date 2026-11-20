"""Cart endpoints against PostgreSQL with a small hand-made catalog."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.adapters.persistence.orm.catalog import Brand, Category, Product
from app.adapters.persistence.orm.stock import Inventory, Price, Warehouse

pytestmark = pytest.mark.integration

HEADERS = {"X-Session-Id": "session-a"}
OTHER = {"X-Session-Id": "session-b"}


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
    """MN-001: 5 + 3 units in two warehouses. MN-002: 7 units. MN-003 inactive. MN-004 no price."""
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
            product("MN-001", "Vision 24", image_url="https://example.com/1.png"),
            product("MN-002", "Office 27"),
            product("MN-003", "Legacy 22", active=False),
            product("MN-004", "Unpriced 30"),
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
            stock("MN-004", "W1", 2),
        ]
    )
    db_session.flush()


def add(client: TestClient, product_id: str, quantity: int, headers=HEADERS):
    return client.post(
        "/api/cart/items", json={"product_id": product_id, "quantity": quantity}, headers=headers
    )


def cart(client: TestClient, headers=HEADERS) -> dict:
    response = client.get("/api/cart", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def inventory(db_session: Session) -> list[tuple]:
    rows = db_session.execute(
        text(
            "SELECT product_id, warehouse_id, on_hand_qty, reserved_qty, available_qty "
            "FROM inventory ORDER BY 1, 2"
        )
    )
    return [tuple(row) for row in rows]


def test_empty_cart(client: TestClient):
    assert cart(client) == {"items": [], "item_count": 0, "total": 0.0, "currency": "USD"}


def test_add_item_returns_cart_with_current_data(client: TestClient):
    response = add(client, "MN-001", 2)
    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "product_id": "MN-001",
                "name": "Vision 24",
                "image_url": "https://example.com/1.png",
                "unit_price": 100.0,
                "quantity": 2,
                "line_total": 200.0,
                "available_qty": 8,
            }
        ],
        "item_count": 2,
        "total": 200.0,
        "currency": "USD",
    }


def test_add_accumulates_and_orders_items(client: TestClient):
    add(client, "MN-002", 1)
    add(client, "MN-001", 2)
    body = add(client, "MN-001", 3).json()
    assert [(i["product_id"], i["quantity"]) for i in body["items"]] == [
        ("MN-001", 5),
        ("MN-002", 1),
    ]
    assert body["item_count"] == 6
    assert body["total"] == 519.99


def test_add_exactly_available_is_allowed(client: TestClient):
    assert add(client, "MN-002", 7).status_code == 200


def test_add_beyond_stock_returns_insufficient_stock_and_keeps_cart(client: TestClient):
    add(client, "MN-001", 6)
    response = add(client, "MN-001", 3)
    assert response.status_code == 409
    assert response.json() == {
        "error": {
            "code": "INSUFFICIENT_STOCK",
            "message": "Solo hay 8 unidades disponibles.",
            "details": {"product_id": "MN-001", "available_qty": 8},
        }
    }
    assert cart(client)["items"][0]["quantity"] == 6


def test_add_50_when_7_are_available(client: TestClient):
    response = add(client, "MN-002", 50)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INSUFFICIENT_STOCK"
    assert response.json()["error"]["details"] == {"product_id": "MN-002", "available_qty": 7}
    assert cart(client)["items"] == []


def test_insufficient_stock_message_is_singular_for_one_unit(
    client: TestClient, db_session: Session
):
    db_session.execute(text("UPDATE inventory SET available_qty = 1 WHERE product_id = 'MN-002'"))
    response = add(client, "MN-002", 2)
    assert response.json()["error"]["message"] == "Solo hay 1 unidad disponible."


def test_insufficient_stock_message_says_there_is_no_stock_instead_of_zero_units(
    client: TestClient, db_session: Session
):
    db_session.execute(text("UPDATE inventory SET available_qty = 0 WHERE product_id = 'MN-002'"))
    response = add(client, "MN-002", 1)
    assert response.status_code == 409
    error = response.json()["error"]
    assert error["message"] == "Este producto no tiene stock en este momento."
    assert error["details"] == {"product_id": "MN-002", "available_qty": 0}


def test_add_inactive_product(client: TestClient):
    response = add(client, "MN-003", 1)
    assert response.status_code == 409
    assert response.json() == {
        "error": {
            "code": "PRODUCT_INACTIVE",
            "message": "El producto ya no se vende.",
            "details": {"product_id": "MN-003"},
        }
    }


def test_add_product_without_price_is_not_sellable(client: TestClient):
    response = add(client, "MN-004", 1)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "PRODUCT_INACTIVE"


def test_add_unknown_product(client: TestClient):
    response = add(client, "NOPE", 1)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "PRODUCT_NOT_FOUND"


def test_patch_sets_quantity(client: TestClient):
    add(client, "MN-001", 5)
    response = client.patch("/api/cart/items/MN-001", json={"quantity": 2}, headers=HEADERS)
    assert response.status_code == 200
    assert response.json()["items"][0]["quantity"] == 2
    assert response.json()["total"] == 200.0


def test_patch_above_stock(client: TestClient):
    add(client, "MN-002", 2)
    response = client.patch("/api/cart/items/MN-002", json={"quantity": 8}, headers=HEADERS)
    assert response.status_code == 409
    assert response.json()["error"]["details"] == {"product_id": "MN-002", "available_qty": 7}
    assert cart(client)["items"][0]["quantity"] == 2


def test_patch_item_not_in_cart(client: TestClient):
    response = client.patch("/api/cart/items/MN-001", json={"quantity": 1}, headers=HEADERS)
    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "PRODUCT_NOT_FOUND",
            "message": "El producto no está en el carrito.",
            "details": {"product_id": "MN-001"},
        }
    }


def test_delete_item_and_idempotency(client: TestClient):
    add(client, "MN-001", 1)
    add(client, "MN-002", 1)
    response = client.delete("/api/cart/items/MN-001", headers=HEADERS)
    assert response.status_code == 200
    assert [i["product_id"] for i in response.json()["items"]] == ["MN-002"]
    again = client.delete("/api/cart/items/MN-001", headers=HEADERS)
    assert again.status_code == 200
    assert again.json() == response.json()
    assert client.delete("/api/cart/items/NOPE", headers=HEADERS).status_code == 200


def test_clear_cart(client: TestClient):
    add(client, "MN-001", 1)
    response = client.delete("/api/cart", headers=HEADERS)
    assert response.status_code == 200
    assert response.json()["items"] == []
    assert client.delete("/api/cart", headers=HEADERS).status_code == 200


def test_sessions_have_separate_carts(client: TestClient):
    add(client, "MN-001", 2)
    add(client, "MN-002", 1, headers=OTHER)
    assert [i["product_id"] for i in cart(client)["items"]] == ["MN-001"]
    assert [i["product_id"] for i in cart(client, OTHER)["items"]] == ["MN-002"]
    client.delete("/api/cart", headers=OTHER)
    assert len(cart(client)["items"]) == 1


def test_price_and_stock_changes_show_up_on_the_next_read(client: TestClient, db_session: Session):
    add(client, "MN-001", 2)
    before = cart(client)["items"][0]
    assert (before["unit_price"], before["available_qty"]) == (100.0, 8)

    db_session.execute(text("UPDATE prices SET current_price = 90.50 WHERE product_id = 'MN-001'"))
    db_session.execute(
        text(
            "UPDATE inventory SET available_qty = 1 WHERE product_id = 'MN-001' "
            "AND warehouse_id = 'W1'"
        )
    )
    after = cart(client)
    assert after["items"][0]["unit_price"] == 90.5
    assert after["items"][0]["line_total"] == 181.0
    assert after["items"][0]["available_qty"] == 4
    assert after["total"] == 181.0


def test_cart_operations_never_change_stock(client: TestClient, db_session: Session):
    before = inventory(db_session)
    add(client, "MN-001", 8)
    client.patch("/api/cart/items/MN-001", json={"quantity": 3}, headers=HEADERS)
    add(client, "MN-002", 50)
    client.delete("/api/cart/items/MN-001", headers=HEADERS)
    client.delete("/api/cart", headers=HEADERS)
    assert inventory(db_session) == before


def test_missing_session_header(client: TestClient):
    for response in (
        client.get("/api/cart"),
        client.post("/api/cart/items", json={"product_id": "MN-001", "quantity": 1}),
        client.patch("/api/cart/items/MN-001", json={"quantity": 1}),
        client.delete("/api/cart/items/MN-001"),
        client.delete("/api/cart"),
    ):
        assert response.status_code == 400
        assert response.json() == {
            "error": {
                "code": "MISSING_SESSION",
                "message": "Falta el identificador de sesión (encabezado X-Session-Id).",
                "details": None,
            }
        }


@pytest.mark.parametrize("session_id", ["", "   ", "x" * 65])
def test_blank_or_too_long_session_id(client: TestClient, session_id: str):
    response = client.get("/api/cart", headers={"X-Session-Id": session_id})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_session_id_of_64_characters_is_accepted(client: TestClient):
    assert client.get("/api/cart", headers={"X-Session-Id": "x" * 64}).status_code == 200


@pytest.mark.parametrize("quantity", [0, -1, 1001])
def test_invalid_quantity_gives_validation_error(client: TestClient, quantity: int):
    for response in (
        add(client, "MN-001", quantity),
        client.patch("/api/cart/items/MN-001", json={"quantity": quantity}, headers=HEADERS),
    ):
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert cart(client)["items"] == []


def test_malformed_body_gives_validation_error(client: TestClient):
    for body in ({}, {"product_id": "MN-001"}, {"product_id": "MN-001", "quantity": "many"}):
        response = client.post("/api/cart/items", json=body, headers=HEADERS)
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"
