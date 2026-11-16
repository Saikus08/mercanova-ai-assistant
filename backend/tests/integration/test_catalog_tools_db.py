"""Catalog tools against PostgreSQL: price and stock are read on every call, not from the index."""

from decimal import Decimal

import pytest
from sqlalchemy import text, update
from sqlalchemy.orm import Session

from app.adapters.persistence.catalog_repository import SqlAlchemyCatalogRepository
from app.adapters.persistence.orm.catalog import (
    EMBEDDING_DIMENSIONS,
    Brand,
    Category,
    Product,
    ProductEmbedding,
    ProductRelation,
    ProductSpecification,
)
from app.adapters.persistence.orm.stock import Inventory, Price, Warehouse
from app.adapters.persistence.semantic_search_repository import SqlAlchemySemanticSearch
from app.application.agent.catalog_tools import build_catalog_tools
from app.application.agent.dispatcher import ToolDispatcher
from app.application.agent.registry import ToolRegistry
from app.application.agent.tool import ToolContext

pytestmark = pytest.mark.integration

MODEL = "fake-model"
CONTEXT = ToolContext(session_id="s1")
MIN_SIMILARITY = 0.4


def vec(*weights: tuple[int, float]) -> list[float]:
    values = [0.0] * EMBEDDING_DIMENSIONS
    for index, weight in weights:
        values[index] = weight
    return values


# Scores against the query: P1 0.894, P2 0.447, P3 0.0 (below the threshold).
QUERY = vec((0, 1.0), (1, 0.5))


class FakeEmbedder:
    index_id = MODEL

    def embed_query(self, text: str) -> list[float]:
        return QUERY


@pytest.fixture(autouse=True)
def catalog_data(db_session: Session) -> None:
    db_session.add_all(
        [
            Brand(brand_id="B1", brand_name="Flux"),
            Category(
                subcategory_id="SC-GAM",
                subcategory_name="Gaming",
                category_id="C-MON",
                category_name="Monitors",
            ),
            Category(
                subcategory_id="SC-HEA",
                subcategory_name="Headphones",
                category_id="C-AUD",
                category_name="Audio",
            ),
            Warehouse(warehouse_id="W1", warehouse_name="Centro", city="Montevideo"),
            Warehouse(warehouse_id="W2", warehouse_name="Costa", city="Punta del Este"),
        ]
    )
    db_session.flush()
    for pid, name, sub, price, stock, axis in [
        ("P1", "Vision 24", ("Monitors", "Gaming", "SC-GAM"), "300.00", 5, 0),
        ("P2", "Office 27", ("Monitors", "Gaming", "SC-GAM"), "200.00", 0, 1),
        ("P3", "Buds", ("Audio", "Headphones", "SC-HEA"), "50.00", 7, 10),
        ("P4", "Pro 32", ("Monitors", "Gaming", "SC-GAM"), "400.00", 2, 11),
    ]:
        db_session.add(
            Product(
                product_id=pid,
                sku=f"SKU-{pid}",
                name=name,
                brand_id="B1",
                subcategory_id=sub[2],
                category_name=sub[0],
                subcategory_name=sub[1],
                short_description=f"About {name}",
            )
        )
        db_session.flush()
        db_session.add(
            Price(
                product_id=pid,
                currency="USD",
                list_price=Decimal(price),
                current_price=Decimal(price),
            )
        )
        if stock:
            db_session.add(
                Inventory(product_id=pid, warehouse_id="W1", on_hand_qty=stock, available_qty=stock)
            )
        db_session.add(
            ProductEmbedding(
                product_id=pid,
                content=f"Name: {name}",
                embedding=vec((axis, 1.0)),
                model=MODEL,
            )
        )
    db_session.add_all(
        [
            ProductSpecification(
                product_id="P1",
                attribute_group="Display",
                attribute_name="Size",
                value_number=Decimal("24"),
                unit="in",
            ),
            ProductSpecification(
                product_id="P2",
                attribute_group="Display",
                attribute_name="Size",
                value_number=Decimal("27"),
                unit="in",
            ),
            ProductRelation(
                product_id="P1",
                related_product_id="P2",
                relation_type="alternative_to",
                strength=Decimal("0.60"),
            ),
            ProductRelation(
                product_id="P1",
                related_product_id="P4",
                relation_type="alternative_to",
                strength=Decimal("0.90"),
            ),
            ProductRelation(
                product_id="P1",
                related_product_id="P3",
                relation_type="accessory_for",
                strength=Decimal("0.99"),
            ),
        ]
    )
    db_session.flush()


@pytest.fixture
def dispatcher(db_session: Session) -> ToolDispatcher:
    tools = build_catalog_tools(
        SqlAlchemyCatalogRepository(db_session),
        FakeEmbedder(),
        SqlAlchemySemanticSearch(db_session),
        MIN_SIMILARITY,
    )
    return ToolDispatcher(ToolRegistry(tools))


def product_ids(result) -> list[str]:
    return [p["product_id"] for p in result.payload["products"]]


def test_search_returns_current_price_and_stock_and_drops_dissimilar_products(dispatcher):
    result = dispatcher.dispatch("search_products", {"query": "gaming monitor"}, CONTEXT)

    assert result.ok is True
    assert product_ids(result) == ["P1", "P2"]  # P3 scores 0.0, below the threshold
    first = result.payload["products"][0]
    assert first["price"]["current"] == 300.0
    assert first["available_qty"] == 5
    assert first["similarity"] == pytest.approx(0.894, abs=0.001)


def test_search_reads_the_new_price_and_stock_when_the_database_changes(
    dispatcher, db_session: Session
):
    before = dispatcher.dispatch("search_products", {"query": "gaming monitor"}, CONTEXT)
    db_session.execute(
        update(Price).where(Price.product_id == "P1").values(current_price=Decimal("249.90"))
    )
    db_session.execute(
        update(Inventory).where(Inventory.product_id == "P1").values(available_qty=1)
    )
    after = dispatcher.dispatch("search_products", {"query": "gaming monitor"}, CONTEXT)

    assert before.payload["products"][0]["price"]["current"] == 300.0
    assert after.payload["products"][0]["price"]["current"] == 249.9
    assert after.payload["products"][0]["available_qty"] == 1


def test_price_and_stock_tools_read_the_new_values_when_the_database_changes(
    dispatcher, db_session: Session
):
    db_session.execute(
        update(Price).where(Price.product_id == "P1").values(current_price=Decimal("199.00"))
    )
    db_session.execute(
        update(Inventory).where(Inventory.product_id == "P1").values(available_qty=0)
    )

    price = dispatcher.dispatch("get_price", {"product_id": "P1"}, CONTEXT)
    stock = dispatcher.dispatch("get_stock", {"product_id": "P1"}, CONTEXT)

    assert price.payload["price"]["current"] == 199.0
    assert (stock.payload["available_qty"], stock.payload["in_stock"]) == (0, False)


def test_search_returns_only_products_with_stock_when_in_stock_only_is_set(dispatcher):
    result = dispatcher.dispatch(
        "search_products", {"query": "gaming monitor", "in_stock_only": True}, CONTEXT
    )

    assert product_ids(result) == ["P1"]  # P2 has no stock


def test_search_returns_a_note_when_filters_leave_no_similar_product(dispatcher):
    result = dispatcher.dispatch(
        "search_products", {"query": "gaming monitor", "category": "Audio"}, CONTEXT
    )

    assert result.ok is True
    assert result.payload["count"] == 0
    assert "do not invent" in result.payload["note"]


@pytest.mark.parametrize(
    "tool", ["get_product_details", "get_price", "get_stock", "get_alternatives"]
)
def test_tools_return_a_not_found_error_when_the_product_id_does_not_exist(dispatcher, tool):
    result = dispatcher.dispatch(tool, {"product_id": "NOPE"}, CONTEXT)

    assert result.ok is False
    assert "NOPE" in result.payload["error"]
    assert "search_products" in result.payload["hint"]


def test_product_details_include_specifications_and_warehouse_stock(dispatcher):
    result = dispatcher.dispatch("get_product_details", {"product_id": "P1"}, CONTEXT)

    assert result.payload["specifications"] == [
        {"group": "Display", "name": "Size", "value": "24", "unit": "in"}
    ]
    assert [w["warehouse_id"] for w in result.payload["warehouses"]] == ["W1"]
    assert result.payload["price"]["currency"] == "USD"


def test_compare_aligns_specifications_and_reports_unknown_products(dispatcher):
    result = dispatcher.dispatch("compare_products", {"product_ids": ["P1", "P2"]}, CONTEXT)

    assert [p["product_id"] for p in result.payload["products"]] == ["P1", "P2"]
    assert result.payload["attributes"][0]["values"] == {"P1": "24", "P2": "27"}

    missing = dispatcher.dispatch("compare_products", {"product_ids": ["P1", "NOPE"]}, CONTEXT)
    assert missing.ok is False
    assert "NOPE" in missing.payload["error"]


def test_alternatives_return_only_alternative_to_relations_strongest_first(dispatcher):
    result = dispatcher.dispatch("get_alternatives", {"product_id": "P1"}, CONTEXT)

    assert [a["product_id"] for a in result.payload["alternatives"]] == ["P4", "P2"]
    assert result.payload["alternatives"][0]["relation_strength"] == 0.9
    assert result.payload["alternatives"][0]["price"]["current"] == 400.0
    assert result.payload["alternatives"][1]["in_stock"] is False
    assert "P3" not in str(result.payload)  # accessory_for is not an alternative


def test_tools_read_fresh_values_when_another_transaction_changed_them_behind_the_orm(
    dispatcher, db_session: Session
):
    """Raw SQL is invisible to the session identity map: only a real re-read sees it."""
    dispatcher.dispatch("get_price", {"product_id": "P1"}, CONTEXT)
    dispatcher.dispatch("search_products", {"query": "gaming monitor"}, CONTEXT)
    db_session.execute(text("UPDATE prices SET current_price = 111.11 WHERE product_id = 'P1'"))
    db_session.execute(text("UPDATE inventory SET available_qty = 0 WHERE product_id = 'P1'"))

    price = dispatcher.dispatch("get_price", {"product_id": "P1"}, CONTEXT)
    found = dispatcher.dispatch("search_products", {"query": "gaming monitor"}, CONTEXT)
    stock = dispatcher.dispatch("get_stock", {"product_id": "P1"}, CONTEXT)

    assert price.payload["price"]["current"] == 111.11
    assert found.payload["products"][0]["price"]["current"] == 111.11
    assert stock.payload["available_qty"] == 0
