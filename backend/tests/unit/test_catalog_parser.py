"""Dataset rows are turned into validated records; invalid rows are rejected with a reason."""

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from app.adapters.dataset.catalog_parser import (
    SHEET_COLUMNS,
    DatasetStructureError,
    SheetData,
    SheetRow,
    parse_brands,
    parse_catalog,
    parse_categories,
    parse_inventory,
    parse_prices,
    parse_products,
    parse_relations,
    parse_specifications,
)

CATEGORY_INDEX = {("monitors", "gaming"): "SUB003"}


def _rows(*values: dict[str, object]) -> list[SheetRow]:
    """Sheet rows numbered as in Excel: the header is row 1, data starts at row 2."""
    return [SheetRow(number=index + 2, values=row) for index, row in enumerate(values)]


def _product(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "product_id": "MN-MON-0001",
        "sku": "MON-10000",
        "name": "Flux Vision 24 QHD IPS",
        "brand": "Flux",
        "brand_id": "BR020",
        "category": "Monitors",
        "subcategory": "Gaming",
        "short_description": "24-inch QHD IPS monitor.",
        "description": "Designed for office work.",
        "recommended_for": "office work; programming",
        "not_recommended_for": None,
        "key_features": "24-inch; QHD",
        "tags": "monitor; display",
        "color": "Black",
        "weight_kg": 6.74,
        "width_cm": 50.4,
        "height_cm": 32.4,
        "depth_cm": 23.9,
        "warranty_months": 12,
        "return_days": 30,
        "rating": 4.3,
        "review_count": 1088,
        "launch_date": datetime(2026, 3, 5),
        "active": True,
        "image_url": "https://placehold.co/800x600/png?text=MON-10000",
    }
    values.update(overrides)
    return values


def _price(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "product_id": "MN-MON-0001",
        "currency": "USD",
        "list_price": 493.28,
        "current_price": 468.62,
        "discount_percent": 5,
        "tax_included": True,
        "price_updated_at": datetime(2026, 10, 17),
    }
    values.update(overrides)
    return values


def test_parse_products_builds_record_when_row_is_valid() -> None:
    result = parse_products(_rows(_product()), {"BR020"}, CATEGORY_INDEX)

    assert result.rejected == []
    [product] = result.records
    assert product.product_id == "MN-MON-0001"
    assert product.subcategory_id == "SUB003"
    assert product.category_name == "Monitors"
    assert product.rating == Decimal("4.30")
    assert product.weight_kg == Decimal("6.740")
    assert product.launch_date == date(2026, 3, 5)


def test_parse_products_splits_and_trims_list_columns_when_separated_by_semicolons() -> None:
    row = _product(recommended_for=" office work ;programming;; gaming ", not_recommended_for=None)

    [product] = parse_products(_rows(row), {"BR020"}, CATEGORY_INDEX).records

    assert product.recommended_for == ["office work", "programming", "gaming"]
    assert product.not_recommended_for == []
    assert product.tags == ["monitor", "display"]


def test_parse_products_rejects_row_when_required_field_is_missing() -> None:
    result = parse_products(_rows(_product(name="   ")), {"BR020"}, CATEGORY_INDEX)

    assert result.records == []
    [rejected] = result.rejected
    assert (rejected.sheet, rejected.row_number) == ("Products", 2)
    assert "name" in rejected.reason
    assert "required" in rejected.reason.lower()


def test_parse_products_rejects_row_when_rating_is_above_five() -> None:
    result = parse_products(_rows(_product(rating=7)), {"BR020"}, CATEGORY_INDEX)

    [rejected] = result.rejected
    assert "rating" in rejected.reason


def test_parse_products_rejects_row_when_number_column_has_text() -> None:
    result = parse_products(_rows(_product(review_count="many")), {"BR020"}, CATEGORY_INDEX)

    [rejected] = result.rejected
    assert "review_count" in rejected.reason


def test_parse_products_rejects_row_when_brand_is_unknown() -> None:
    result = parse_products(_rows(_product(brand_id="BR999")), {"BR020"}, CATEGORY_INDEX)

    [rejected] = result.rejected
    assert "BR999" in rejected.reason


def test_parse_products_rejects_row_when_category_pair_is_unknown() -> None:
    row = _product(subcategory="Office")

    result = parse_products(_rows(row), {"BR020"}, CATEGORY_INDEX)

    [rejected] = result.rejected
    assert "Monitors / Office" in rejected.reason


def test_parse_products_rejects_second_row_when_product_id_repeats() -> None:
    rows = _rows(_product(), _product(sku="MON-99999"))

    result = parse_products(rows, {"BR020"}, CATEGORY_INDEX)

    assert len(result.records) == 1
    [rejected] = result.rejected
    assert rejected.row_number == 3
    assert "duplicate product_id" in rejected.reason


def test_parse_prices_builds_record_when_row_is_valid() -> None:
    result = parse_prices(_rows(_price()), {"MN-MON-0001"})

    [price] = result.records
    assert price.current_price == Decimal("468.62")
    assert price.price_updated_at == datetime(2026, 10, 17, tzinfo=UTC)


def test_parse_prices_rejects_row_when_price_is_negative() -> None:
    result = parse_prices(_rows(_price(current_price=-1)), {"MN-MON-0001"})

    assert result.records == []
    [rejected] = result.rejected
    assert "current_price" in rejected.reason


def test_parse_prices_rejects_row_when_discount_is_above_one_hundred() -> None:
    result = parse_prices(_rows(_price(discount_percent=120)), {"MN-MON-0001"})

    [rejected] = result.rejected
    assert "discount_percent" in rejected.reason


def test_parse_prices_rejects_row_when_product_is_unknown() -> None:
    result = parse_prices(_rows(_price(product_id="MN-XXX-0001")), {"MN-MON-0001"})

    assert result.records == []
    [rejected] = result.rejected
    assert "unknown product_id 'MN-XXX-0001'" in rejected.reason


def test_parse_inventory_rejects_row_when_quantity_is_negative() -> None:
    row = {
        "product_id": "MN-MON-0001",
        "warehouse_id": "WH-MVD-CEN",
        "on_hand_qty": -3,
        "reserved_qty": 0,
        "available_qty": 0,
        "inventory_status": "Out of stock",
        "inventory_updated_at": None,
    }

    result = parse_inventory(_rows(row), {"MN-MON-0001"}, {"WH-MVD-CEN"})

    [rejected] = result.rejected
    assert "on_hand_qty" in rejected.reason


def test_parse_inventory_rejects_row_when_warehouse_is_unknown() -> None:
    row = {
        "product_id": "MN-MON-0001",
        "warehouse_id": "WH-NOPE",
        "on_hand_qty": 3,
        "reserved_qty": 0,
        "available_qty": 3,
    }

    result = parse_inventory(_rows(row), {"MN-MON-0001"}, {"WH-MVD-CEN"})

    [rejected] = result.rejected
    assert "unknown warehouse_id 'WH-NOPE'" in rejected.reason


def test_parse_specifications_rejects_row_when_it_has_no_value() -> None:
    row = {
        "product_id": "MN-MON-0001",
        "attribute_group": "Display",
        "attribute_name": "Screen Size",
        "value_text": None,
        "value_number": None,
        "unit": "in",
    }

    result = parse_specifications(_rows(row), {"MN-MON-0001"})

    [rejected] = result.rejected
    assert "value_text or value_number" in rejected.reason


def test_parse_relations_rejects_row_when_product_relates_to_itself() -> None:
    row = {
        "product_id": "MN-MON-0001",
        "related_product_id": "MN-MON-0001",
        "relation_type": "alternative_to",
        "strength": 0.8,
    }

    result = parse_relations(_rows(row), {"MN-MON-0001"})

    [rejected] = result.rejected
    assert "itself" in rejected.reason


def test_parse_categories_rejects_row_when_category_pair_repeats() -> None:
    base = {"category_id": "CAT01", "category_name": "Monitors", "department": "Electronics"}
    rows = _rows(
        {**base, "subcategory_id": "SUB001", "subcategory_name": "Office", "sort_order": 11},
        {**base, "subcategory_id": "SUB009", "subcategory_name": "office", "sort_order": 19},
    )

    result = parse_categories(rows)

    assert [category.subcategory_id for category in result.records] == ["SUB001"]
    [rejected] = result.rejected
    assert "duplicate" in rejected.reason


def test_parse_brands_counts_every_row_read() -> None:
    rows = _rows({"brand_id": "BR001", "brand_name": "NovaTech"}, {"brand_id": "BR002"})

    result = parse_brands(rows)

    assert (result.read, len(result.records), len(result.rejected)) == (2, 1, 1)


def test_parse_catalog_fails_when_a_sheet_is_missing() -> None:
    sheets = {name: SheetData(name, columns, []) for name, columns in SHEET_COLUMNS.items()}
    del sheets["Pricing"]

    with pytest.raises(DatasetStructureError, match="Pricing"):
        parse_catalog(sheets)


def test_parse_catalog_fails_when_a_column_is_missing() -> None:
    sheets = {name: SheetData(name, columns, []) for name, columns in SHEET_COLUMNS.items()}
    brands_columns = tuple(c for c in SHEET_COLUMNS["Brands"] if c != "brand_name")
    sheets["Brands"] = SheetData("Brands", brands_columns, [])

    with pytest.raises(DatasetStructureError, match="brand_name"):
        parse_catalog(sheets)


def test_parse_catalog_drops_children_of_rejected_products() -> None:
    sheets = {name: SheetData(name, columns, []) for name, columns in SHEET_COLUMNS.items()}
    sheets["Brands"] = SheetData(
        "Brands", SHEET_COLUMNS["Brands"], _rows({"brand_id": "BR020", "brand_name": "Flux"})
    )
    sheets["Categories"] = SheetData(
        "Categories",
        SHEET_COLUMNS["Categories"],
        _rows(
            {
                "category_id": "CAT01",
                "category_name": "Monitors",
                "subcategory_id": "SUB003",
                "subcategory_name": "Gaming",
            }
        ),
    )
    sheets["Products"] = SheetData("Products", SHEET_COLUMNS["Products"], _rows(_product(rating=9)))
    sheets["Pricing"] = SheetData("Pricing", SHEET_COLUMNS["Pricing"], _rows(_price()))

    catalog = parse_catalog(sheets)

    assert catalog.products.rejected and catalog.prices.rejected
    assert catalog.prices.records == []
