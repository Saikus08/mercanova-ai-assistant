"""Catalog endpoints against PostgreSQL with a small hand-made dataset."""

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.adapters.persistence.orm.catalog import (
    Brand,
    Category,
    Product,
    ProductRelation,
    ProductSpecification,
)
from app.adapters.persistence.orm.stock import Inventory, Price, Warehouse

pytestmark = pytest.mark.integration


def make_product(
    product_id: str, name: str, brand_id: str, sub: tuple[str, str, str], **extra
) -> Product:
    category_name, subcategory_name, subcategory_id = sub
    return Product(
        product_id=product_id,
        sku=f"SKU-{product_id}",
        name=name,
        brand_id=brand_id,
        subcategory_id=subcategory_id,
        category_name=category_name,
        subcategory_name=subcategory_name,
        **extra,
    )


def make_price(product_id: str, current: str, list_price: str, discount: str = "0") -> Price:
    return Price(
        product_id=product_id,
        currency="USD",
        list_price=Decimal(list_price),
        current_price=Decimal(current),
        discount_percent=Decimal(discount),
    )


def make_stock(product_id: str, warehouse_id: str, qty: int) -> Inventory:
    return Inventory(
        product_id=product_id, warehouse_id=warehouse_id, on_hand_qty=qty, available_qty=qty
    )


GAMING = ("Monitors", "Gaming", "SC-GAM")
OFFICE = ("Monitors", "Office", "SC-OFF")
HEADPHONES = ("Audio", "Headphones", "SC-HEA")


@pytest.fixture(autouse=True)
def catalog_data(db_session: Session) -> None:
    """Five products: in stock, out of stock, cheap audio, inactive, and one without price/stock."""
    db_session.add_all(
        [
            Brand(brand_id="B1", brand_name="Flux"),
            Brand(brand_id="B2", brand_name="Orbit"),
            Category(
                subcategory_id="SC-GAM",
                subcategory_name="Gaming",
                category_id="C-MON",
                category_name="Monitors",
                sort_order=1,
            ),
            Category(
                subcategory_id="SC-OFF",
                subcategory_name="Office",
                category_id="C-MON",
                category_name="Monitors",
                sort_order=2,
            ),
            Category(
                subcategory_id="SC-HEA",
                subcategory_name="Headphones",
                category_id="C-AUD",
                category_name="Audio",
                sort_order=1,
            ),
            Warehouse(
                warehouse_id="W1",
                warehouse_name="Centro",
                city="Montevideo",
                department="Montevideo",
                country="UY",
                pickup_enabled=True,
                shipping_enabled=True,
            ),
            Warehouse(
                warehouse_id="W2",
                warehouse_name="Costa",
                city="Punta del Este",
                department="Maldonado",
                country="UY",
                pickup_enabled=False,
                shipping_enabled=True,
            ),
        ]
    )
    db_session.flush()
    db_session.add_all(
        [
            make_product(
                "MN-001",
                "Vision 24",
                "B1",
                GAMING,
                short_description="24 inch gaming monitor",
                description="Long text",
                rating=Decimal("4.5"),
                review_count=10,
                color="Black",
                recommended_for=["gaming"],
                not_recommended_for=["printing"],
                key_features=["QHD", "240 Hz"],
                tags=["monitor"],
                width_cm=Decimal("50.4"),
                height_cm=Decimal("32.4"),
                depth_cm=Decimal("23.9"),
                weight_kg=Decimal("6.74"),
                warranty_months=12,
                return_days=30,
                image_url="https://example.com/1.png",
            ),
            make_product(
                "MN-002", "Office 27", "B1", OFFICE, rating=Decimal("4.0"), review_count=3
            ),
            make_product(
                "MN-003",
                "Buds",
                "B2",
                HEADPHONES,
                short_description="Wireless earbuds",
                rating=Decimal("4.8"),
                review_count=7,
            ),
            make_product("MN-004", "Legacy 22", "B2", GAMING, active=False, rating=Decimal("3.0")),
            make_product("MN-005", "Pure_Sound 100% Mic", "B2", HEADPHONES),
        ]
    )
    db_session.flush()
    db_session.add_all(
        [
            make_price("MN-001", "100.00", "120.00", "16.67"),
            make_price("MN-002", "200.00", "200.00"),
            make_price("MN-003", "50.00", "50.00"),
            make_price("MN-004", "80.00", "80.00"),
            make_stock("MN-001", "W1", 5),
            make_stock("MN-001", "W2", 3),
            make_stock("MN-002", "W1", 0),
            make_stock("MN-003", "W1", 10),
            make_stock("MN-004", "W1", 2),
            ProductSpecification(
                product_id="MN-001",
                attribute_group="Display",
                attribute_name="Size",
                value_number=Decimal("24"),
                unit="in",
            ),
            ProductSpecification(
                product_id="MN-001",
                attribute_group="Display",
                attribute_name="Panel",
                value_text="IPS",
            ),
            ProductSpecification(
                product_id="MN-002",
                attribute_group="Display",
                attribute_name="Size",
                value_number=Decimal("27.5"),
                unit="in",
            ),
            ProductSpecification(
                product_id="MN-002",
                attribute_group="Power",
                attribute_name="Watts",
                value_number=Decimal("30"),
            ),
            ProductRelation(
                product_id="MN-001",
                related_product_id="MN-002",
                relation_type="alternative_to",
                strength=Decimal("0.82"),
            ),
        ]
    )
    db_session.flush()


def ids(client: TestClient, **params) -> list[str]:
    response = client.get("/api/products", params=params)
    assert response.status_code == 200, response.text
    return [item["product_id"] for item in response.json()["items"]]


# --- list ---------------------------------------------------------------------------------


def test_list_returns_summary_shape_and_hides_inactive(client: TestClient) -> None:
    body = client.get("/api/products").json()

    assert [i["product_id"] for i in body["items"]] == ["MN-001", "MN-002", "MN-003", "MN-005"]
    assert (body["page"], body["page_size"], body["total"]) == (1, 20, 4)
    assert body["items"][0] == {
        "product_id": "MN-001",
        "sku": "SKU-MN-001",
        "name": "Vision 24",
        "brand": "Flux",
        "category": "Monitors",
        "subcategory": "Gaming",
        "short_description": "24 inch gaming monitor",
        "image_url": "https://example.com/1.png",
        "rating": 4.5,
        "review_count": 10,
        "price": {"current": 100.0, "list": 120.0, "discount_percent": 16.67, "currency": "USD"},
        "available_qty": 8,
        "in_stock": True,
    }


def test_list_handles_product_without_price_or_inventory(client: TestClient) -> None:
    items = {i["product_id"]: i for i in client.get("/api/products").json()["items"]}

    assert items["MN-005"]["available_qty"] == 0
    assert items["MN-005"]["in_stock"] is False
    assert items["MN-005"]["price"] is None
    assert items["MN-005"]["rating"] is None


def test_list_filters_by_text_in_name_brand_and_short_description(client: TestClient) -> None:
    assert ids(client, q="vision") == ["MN-001"]
    assert ids(client, q="orbit") == ["MN-003", "MN-005"]
    assert ids(client, q="earbuds") == ["MN-003"]


def test_list_text_filter_escapes_like_wildcards(client: TestClient) -> None:
    assert ids(client, q="%") == ["MN-005"]
    assert ids(client, q="_") == ["MN-005"]
    assert ids(client, q="100%") == ["MN-005"]


def test_list_filters_by_category_subcategory_and_brand(client: TestClient) -> None:
    assert ids(client, category="monitors") == ["MN-001", "MN-002"]
    assert ids(client, subcategory="Office") == ["MN-002"]
    assert ids(client, category="Monitors", subcategory="Headphones") == []
    assert ids(client, brand="Flux") == ["MN-001", "MN-002"]


def test_list_filters_by_price_range(client: TestClient) -> None:
    assert ids(client, min_price=100) == ["MN-001", "MN-002"]
    assert ids(client, max_price=100) == ["MN-001", "MN-003"]
    assert ids(client, min_price=60, max_price=150) == ["MN-001"]


def test_list_filters_by_stock(client: TestClient) -> None:
    assert ids(client, in_stock="true") == ["MN-001", "MN-003"]
    assert ids(client, in_stock="false") == ["MN-002", "MN-005"]


def test_list_sorts_by_price_and_rating_with_stable_tie_break(client: TestClient) -> None:
    assert ids(client, sort="price_asc") == ["MN-003", "MN-001", "MN-002", "MN-005"]
    assert ids(client, sort="price_desc") == ["MN-002", "MN-001", "MN-003", "MN-005"]
    assert ids(client, sort="rating") == ["MN-003", "MN-001", "MN-002", "MN-005"]


def test_list_paginates_and_reports_total(client: TestClient) -> None:
    body = client.get("/api/products", params={"page": 2, "page_size": 3}).json()

    assert [i["product_id"] for i in body["items"]] == ["MN-005"]
    assert (body["page"], body["page_size"], body["total"]) == (2, 3, 4)


def test_list_caps_page_size_at_100(client: TestClient) -> None:
    body = client.get("/api/products", params={"page_size": 500}).json()

    assert body["page_size"] == 100


@pytest.mark.parametrize(
    "params",
    [
        {"page": 0},
        {"page_size": 0},
        {"sort": "cheapest"},
        {"min_price": "abc"},
        {"in_stock": "maybe"},
    ],
)
def test_list_rejects_invalid_params_with_400_error_shape(client: TestClient, params: dict) -> None:
    response = client.get("/api/products", params=params)

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["message"]
    assert "details" in error


def test_price_and_stock_reflect_database_changes_between_requests(
    client: TestClient, db_session: Session
) -> None:
    before = client.get("/api/products/MN-001").json()
    db_session.execute(
        update(Price).where(Price.product_id == "MN-001").values(current_price=Decimal("90.50"))
    )
    db_session.execute(
        update(Inventory)
        .where(Inventory.product_id == "MN-001", Inventory.warehouse_id == "W1")
        .values(available_qty=0)
    )
    after = client.get("/api/products/MN-001").json()
    listed = client.get("/api/products", params={"q": "vision"}).json()["items"][0]

    assert (before["price"]["current"], before["available_qty"]) == (100.0, 8)
    assert (after["price"]["current"], after["available_qty"]) == (90.5, 3)
    assert (listed["price"]["current"], listed["available_qty"]) == (90.5, 3)


# --- detail -------------------------------------------------------------------------------


def test_detail_returns_full_product(client: TestClient) -> None:
    body = client.get("/api/products/MN-001").json()

    assert body["product_id"] == "MN-001"
    assert body["available_qty"] == 8
    assert body["description"] == "Long text"
    assert body["recommended_for"] == ["gaming"]
    assert body["not_recommended_for"] == ["printing"]
    assert body["key_features"] == ["QHD", "240 Hz"]
    assert body["tags"] == ["monitor"]
    assert body["color"] == "Black"
    assert body["dimensions_cm"] == {"width": 50.4, "height": 32.4, "depth": 23.9}
    assert body["weight_kg"] == 6.74
    assert (body["warranty_months"], body["return_days"]) == (12, 30)
    assert {"group": "Display", "name": "Size", "value": "24", "unit": "in"} in body[
        "specifications"
    ]
    assert {"group": "Display", "name": "Panel", "value": "IPS", "unit": None} in body[
        "specifications"
    ]
    assert body["availability"] == [
        {
            "warehouse_id": "W1",
            "warehouse_name": "Centro",
            "city": "Montevideo",
            "available_qty": 5,
            "pickup_enabled": True,
        },
        {
            "warehouse_id": "W2",
            "warehouse_name": "Costa",
            "city": "Punta del Este",
            "available_qty": 3,
            "pickup_enabled": False,
        },
    ]
    assert body["related"] == [
        {
            "product_id": "MN-002",
            "name": "Office 27",
            "relation_type": "alternative_to",
            "strength": 0.82,
        }
    ]


def test_detail_returns_inactive_product(client: TestClient) -> None:
    response = client.get("/api/products/MN-004")

    assert response.status_code == 200
    assert response.json()["product_id"] == "MN-004"


def test_detail_of_product_without_extras_has_empty_collections(client: TestClient) -> None:
    body = client.get("/api/products/MN-005").json()

    assert body["availability"] == []
    assert body["related"] == []
    assert body["specifications"] == []
    assert body["dimensions_cm"] == {"width": None, "height": None, "depth": None}


def test_detail_returns_404_error_shape_when_product_does_not_exist(client: TestClient) -> None:
    response = client.get("/api/products/MN-999")

    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "PRODUCT_NOT_FOUND"
    assert error["details"] == {"product_id": "MN-999"}
    assert error["message"]


# --- compare ------------------------------------------------------------------------------


def test_compare_returns_products_and_attribute_union_with_nulls(client: TestClient) -> None:
    response = client.get("/api/products/compare", params={"ids": "MN-002,MN-001"})

    assert response.status_code == 200
    body = response.json()
    assert [p["product_id"] for p in body["products"]] == ["MN-002", "MN-001"]
    attributes = {(a["group"], a["name"]): a for a in body["attributes"]}
    assert set(attributes) == {("Display", "Size"), ("Display", "Panel"), ("Power", "Watts")}
    assert attributes[("Display", "Size")]["unit"] == "in"
    assert attributes[("Display", "Size")]["values"] == {"MN-002": "27.5", "MN-001": "24"}
    assert attributes[("Display", "Panel")]["values"] == {"MN-002": None, "MN-001": "IPS"}
    assert attributes[("Power", "Watts")]["values"] == {"MN-002": "30", "MN-001": None}


@pytest.mark.parametrize(
    "ids_param", ["MN-001", "MN-001,MN-001", "MN-001,MN-002,MN-003,MN-004,MN-005"]
)
def test_compare_rejects_wrong_number_of_products(client: TestClient, ids_param: str) -> None:
    response = client.get("/api/products/compare", params={"ids": ids_param})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_compare_requires_ids_param(client: TestClient) -> None:
    response = client.get("/api/products/compare")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_compare_returns_404_when_an_id_is_unknown(client: TestClient) -> None:
    response = client.get("/api/products/compare", params={"ids": "MN-001,MN-999"})

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "PRODUCT_NOT_FOUND"
    assert response.json()["error"]["details"] == {"product_id": "MN-999"}


# --- reference data -----------------------------------------------------------------------


def test_categories_are_nested_and_ordered(client: TestClient) -> None:
    body = client.get("/api/categories").json()

    assert body == [
        {"category": "Audio", "subcategories": ["Headphones"]},
        {"category": "Monitors", "subcategories": ["Gaming", "Office"]},
    ]


def test_warehouses_list_all_fields(client: TestClient) -> None:
    body = client.get("/api/warehouses").json()

    assert body == [
        {
            "warehouse_id": "W1",
            "warehouse_name": "Centro",
            "city": "Montevideo",
            "department": "Montevideo",
            "country": "UY",
            "pickup_enabled": True,
            "shipping_enabled": True,
        },
        {
            "warehouse_id": "W2",
            "warehouse_name": "Costa",
            "city": "Punta del Este",
            "department": "Maldonado",
            "country": "UY",
            "pickup_enabled": False,
            "shipping_enabled": True,
        },
    ]


# --- errors -------------------------------------------------------------------------------


def test_unexpected_error_returns_500_without_details(client: TestClient, monkeypatch) -> None:
    def boom(*args, **kwargs):
        raise RuntimeError("secret internal detail")

    monkeypatch.setattr(
        "app.adapters.persistence.catalog_repository.SqlAlchemyCatalogRepository.list_warehouses",
        boom,
    )

    response = client.get("/api/warehouses")

    assert response.status_code == 500
    error = response.json()["error"]
    assert error["code"] == "INTERNAL_ERROR"
    assert error.get("details") is None
    assert "secret" not in response.text


def test_list_rejects_page_too_large_for_sql_offset(client: TestClient) -> None:
    response = client.get("/api/products", params={"page": 99999999999})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_unknown_route_returns_contract_error_body(client: TestClient) -> None:
    response = client.get("/api/nope")

    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "NOT_FOUND", "message": "El recurso no existe.", "details": None}
    }


def test_wrong_method_returns_contract_error_body(client: TestClient) -> None:
    response = client.post("/api/products")

    assert response.status_code == 405
    assert response.json()["error"]["code"] == "METHOD_NOT_ALLOWED"
    assert response.json()["error"]["message"] == "Método no permitido."
    assert "GET" in response.headers["allow"]


def test_missing_product_keeps_its_specific_code(client: TestClient) -> None:
    response = client.get("/api/products/NOPE")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "PRODUCT_NOT_FOUND"
