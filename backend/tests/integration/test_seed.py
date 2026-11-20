"""The seed loads a small Excel into PostgreSQL, skips invalid rows and can run twice."""

from collections.abc import Iterator
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest
from openpyxl import Workbook
from sqlalchemy import Engine, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.adapters.dataset.catalog_parser import SHEET_COLUMNS
from app.adapters.persistence.orm import (
    Brand,
    Category,
    Inventory,
    Price,
    Product,
    ProductRelation,
    ProductSpecification,
    Warehouse,
)
from app.scripts.seed import run_seed

pytestmark = pytest.mark.integration

TABLES = {
    "brands": Brand,
    "categories": Category,
    "warehouses": Warehouse,
    "products": Product,
    "specifications": ProductSpecification,
    "relations": ProductRelation,
    "prices": Price,
    "inventory": Inventory,
}


def _product(product_id: str, sku: str, brand_id: str, subcategory: str, rating: float) -> dict:
    return {
        "product_id": product_id,
        "sku": sku,
        "name": f"Monitor {sku}",
        "brand": "ignored",
        "brand_id": brand_id,
        "category": "Monitors",
        "subcategory": subcategory,
        "recommended_for": "office work; programming",
        "tags": "monitor; display",
        "rating": rating,
        "launch_date": datetime(2026, 3, 5),
        "active": True,
    }


def _sheets(current_price: float = 468.62) -> dict[str, list[dict]]:
    return {
        "Brands": [
            {"brand_id": "BR001", "brand_name": "NovaTech"},
            {"brand_id": "BR002", "brand_name": "Aether"},
        ],
        "Categories": [
            {"category_id": "CAT01", "category_name": "Monitors", "subcategory_id": "SUB001",
             "subcategory_name": "Office", "sort_order": 11},
            {"category_id": "CAT01", "category_name": "Monitors", "subcategory_id": "SUB002",
             "subcategory_name": "Gaming", "sort_order": 12},
        ],
        "Warehouses": [
            {"warehouse_id": "WH-A", "warehouse_name": "Centro", "pickup_enabled": True},
            {"warehouse_id": "WH-B", "warehouse_name": "Este", "pickup_enabled": False},
        ],
        "Products": [
            _product("P1", "SKU-1", "BR001", "Office", 4.3),
            _product("P2", "SKU-2", "BR002", "Gaming", 4.0),
            _product("P3", "SKU-3", "BR001", "Gaming", 7.5),  # invalid: rating above 5
        ],
        "Specifications": [
            {"product_id": "P1", "attribute_group": "Display", "attribute_name": "Screen Size",
             "value_number": 24, "unit": "in"},
            {"product_id": "P1", "attribute_group": "Display", "attribute_name": "Resolution",
             "value_text": "2560x1440"},
            {"product_id": "P3", "attribute_group": "Display", "attribute_name": "Panel",
             "value_text": "IPS"},  # rejected: its product was rejected
        ],
        "Relations": [
            {"product_id": "P1", "related_product_id": "P2", "relation_type": "alternative_to",
             "strength": 0.82},
        ],
        "Pricing": [
            {"product_id": "P1", "currency": "USD", "list_price": 493.28,
             "current_price": current_price, "discount_percent": 5, "tax_included": True,
             "price_updated_at": datetime(2026, 10, 17)},
            {"product_id": "P2", "currency": "USD", "list_price": 574.27,
             "current_price": 574.27, "discount_percent": 0, "tax_included": True},
        ],
        "Inventory": [
            {"product_id": "P1", "warehouse_id": "WH-A", "on_hand_qty": 10, "reserved_qty": 3,
             "available_qty": 7, "inventory_status": "In stock"},
            {"product_id": "P1", "warehouse_id": "WH-B", "on_hand_qty": 0, "reserved_qty": 0,
             "available_qty": 0, "inventory_status": "Out of stock"},
            {"product_id": "P2", "warehouse_id": "WH-A", "on_hand_qty": 4, "reserved_qty": 0,
             "available_qty": 4, "inventory_status": "In stock"},
        ],
    }


def _write_workbook(path: Path, sheets: dict[str, list[dict]]) -> Path:
    workbook = Workbook()
    workbook.remove(workbook.active)
    for name, rows in sheets.items():
        columns = list(SHEET_COLUMNS[name])
        if name == "Products":
            columns.insert(3, "brand")  # the real sheet also has the brand name
        sheet = workbook.create_sheet(name)
        sheet.append(columns)
        for row in rows:
            sheet.append([row.get(column) for column in columns])
    workbook.save(path)
    return path


@pytest.fixture
def session_factory(migrated_engine: Engine) -> Iterator[sessionmaker[Session]]:
    """Sessions inside one outer transaction that is rolled back after the test.

    The seed opens and commits its own transaction; with ``create_savepoint`` that
    commit only releases a savepoint, so nothing outlives the test.
    """
    connection = migrated_engine.connect()
    transaction = connection.begin()
    try:
        yield sessionmaker(bind=connection, join_transaction_mode="create_savepoint")
    finally:
        transaction.rollback()
        connection.close()


def _counts(session_factory: sessionmaker[Session]) -> dict[str, int]:
    with session_factory() as session:
        return {
            name: session.scalar(select(func.count()).select_from(model)) or 0
            for name, model in TABLES.items()
        }


EXPECTED_COUNTS = {
    "brands": 2,
    "categories": 2,
    "warehouses": 2,
    "products": 2,
    "specifications": 2,
    "relations": 1,
    "prices": 2,
    "inventory": 3,
}


def test_seed_loads_valid_rows_when_workbook_has_one_invalid_product(
    tmp_path: Path, session_factory: sessionmaker[Session]
) -> None:
    workbook = _write_workbook(tmp_path / "dataset.xlsx", _sheets())

    run_seed(workbook, session_factory)

    assert _counts(session_factory) == EXPECTED_COUNTS
    with session_factory() as session:
        product = session.get(Product, "P1")
        assert product is not None
        assert product.subcategory_id == "SUB001"
        assert product.recommended_for == ["office work", "programming"]


def test_seed_reports_rejected_rows_with_sheet_row_and_reason(
    tmp_path: Path, session_factory: sessionmaker[Session]
) -> None:
    workbook = _write_workbook(tmp_path / "dataset.xlsx", _sheets())

    report = run_seed(workbook, session_factory)

    summary = {sheet.sheet: (sheet.read, len(sheet.records), len(sheet.rejected))
               for sheet in report.sheets()}
    assert summary["Products"] == (3, 2, 1)
    assert summary["Specifications"] == (3, 2, 1)
    product_rejection = report.products.rejected[0]
    assert product_rejection.row_number == 4
    assert "rating" in product_rejection.reason
    assert "unknown product_id 'P3'" in report.specifications.rejected[0].reason


def test_seed_leaves_same_data_when_run_twice(
    tmp_path: Path, session_factory: sessionmaker[Session]
) -> None:
    workbook = _write_workbook(tmp_path / "dataset.xlsx", _sheets())

    run_seed(workbook, session_factory)
    first = _counts(session_factory)
    run_seed(workbook, session_factory)

    assert _counts(session_factory) == first == EXPECTED_COUNTS


def test_seed_updates_existing_rows_when_dataset_changes(
    tmp_path: Path, session_factory: sessionmaker[Session]
) -> None:
    run_seed(_write_workbook(tmp_path / "v1.xlsx", _sheets()), session_factory)

    run_seed(_write_workbook(tmp_path / "v2.xlsx", _sheets(current_price=450.00)), session_factory)

    with session_factory() as session:
        price = session.get(Price, "P1")
        assert price is not None
        assert price.current_price == Decimal("450.00")
    assert _counts(session_factory) == EXPECTED_COUNTS


def test_seed_loads_nothing_when_the_database_rejects_a_row(
    tmp_path: Path, session_factory: sessionmaker[Session]
) -> None:
    # An existing product already uses SKU-2, so inserting P2 violates the unique SKU.
    with session_factory() as session, session.begin():
        session.add(Brand(brand_id="BR900", brand_name="Existing"))
        session.flush()
        session.add(Product(product_id="P900", sku="SKU-2", name="Existing", brand_id="BR900",
                            category_name="Monitors", subcategory_name="Office"))
    workbook = _write_workbook(tmp_path / "dataset.xlsx", _sheets())

    with pytest.raises(IntegrityError):
        run_seed(workbook, session_factory)

    counts = _counts(session_factory)
    assert counts["brands"] == 1  # only the pre-existing brand
    assert counts["products"] == 1
    assert counts["categories"] == counts["warehouses"] == 0


# --- stock of orders already confirmed ------------------------------------------------------


def _sell_one_unit_of_p1(session_factory: sessionmaker[Session]) -> None:
    """What confirming an order does to the stock of P1 in WH-A (on hand and available drop)."""
    with session_factory() as session, session.begin():
        session.execute(
            update(Inventory)
            .where(Inventory.product_id == "P1", Inventory.warehouse_id == "WH-A")
            .values(
                on_hand_qty=Inventory.on_hand_qty - 1,
                available_qty=Inventory.available_qty - 1,
            )
        )


def _p1_stock(session_factory: sessionmaker[Session]) -> tuple[int, int]:
    with session_factory() as session:
        row = session.get(Inventory, ("P1", "WH-A"))
        assert row is not None
        return row.on_hand_qty, row.available_qty


def test_seed_keeps_the_stock_left_by_confirmed_orders(
    tmp_path: Path, session_factory: sessionmaker[Session]
) -> None:
    workbook = _write_workbook(tmp_path / "dataset.xlsx", _sheets())
    run_seed(workbook, session_factory)
    _sell_one_unit_of_p1(session_factory)

    run_seed(workbook, session_factory)

    assert _p1_stock(session_factory) == (9, 6)


def test_seed_with_reset_stock_restores_the_quantities_of_the_dataset(
    tmp_path: Path, session_factory: sessionmaker[Session]
) -> None:
    workbook = _write_workbook(tmp_path / "dataset.xlsx", _sheets())
    run_seed(workbook, session_factory)
    _sell_one_unit_of_p1(session_factory)

    run_seed(workbook, session_factory, reset_stock=True)

    assert _p1_stock(session_factory) == (10, 7)


def test_seed_loads_the_stock_of_new_rows_without_touching_the_existing_ones(
    tmp_path: Path, session_factory: sessionmaker[Session]
) -> None:
    run_seed(_write_workbook(tmp_path / "v1.xlsx", _sheets()), session_factory)
    _sell_one_unit_of_p1(session_factory)
    v2 = _sheets()
    v2["Inventory"].append(
        {"product_id": "P2", "warehouse_id": "WH-B", "on_hand_qty": 5, "reserved_qty": 0,
         "available_qty": 5, "inventory_status": "In stock"}
    )

    run_seed(_write_workbook(tmp_path / "v2.xlsx", v2), session_factory)

    assert _p1_stock(session_factory) == (9, 6)
    assert _counts(session_factory)["inventory"] == 4
