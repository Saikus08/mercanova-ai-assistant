"""Turn the dataset sheets into validated records, without touching the database.

Each ``parse_*`` function returns the valid records and the rejected rows with
their reason. Foreign keys are checked against the *valid* parent records, so a
row whose parent was rejected is rejected too instead of breaking the load.
"""

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ValidationError

from app.adapters.dataset.records import (
    BrandRecord,
    CategoryRecord,
    InventoryRecord,
    PriceRecord,
    ProductRecord,
    RelationRecord,
    SpecificationRecord,
    WarehouseRecord,
)

# Columns each sheet must have. Extra columns (such as the brand name in Products) are ignored.
SHEET_COLUMNS: dict[str, tuple[str, ...]] = {
    "Brands": ("brand_id", "brand_name", "country_of_origin", "positioning"),
    "Categories": (
        "category_id",
        "category_name",
        "subcategory_id",
        "subcategory_name",
        "department",
        "sort_order",
    ),
    "Warehouses": (
        "warehouse_id",
        "warehouse_name",
        "city",
        "department",
        "country",
        "pickup_enabled",
        "shipping_enabled",
    ),
    "Products": (
        "product_id",
        "sku",
        "name",
        "brand_id",
        "category",
        "subcategory",
        "short_description",
        "description",
        "recommended_for",
        "not_recommended_for",
        "key_features",
        "tags",
        "color",
        "weight_kg",
        "width_cm",
        "height_cm",
        "depth_cm",
        "warranty_months",
        "return_days",
        "rating",
        "review_count",
        "launch_date",
        "active",
        "image_url",
    ),
    "Specifications": (
        "product_id",
        "attribute_group",
        "attribute_name",
        "value_text",
        "value_number",
        "unit",
    ),
    "Relations": ("product_id", "related_product_id", "relation_type", "strength"),
    "Pricing": (
        "product_id",
        "currency",
        "list_price",
        "current_price",
        "discount_percent",
        "tax_included",
        "price_updated_at",
    ),
    "Inventory": (
        "product_id",
        "warehouse_id",
        "on_hand_qty",
        "reserved_qty",
        "available_qty",
        "inventory_status",
        "inventory_updated_at",
    ),
}

CategoryIndex = Mapping[tuple[str, str], str]
"""(category_name, subcategory_name), case-folded → subcategory_id."""


class DatasetStructureError(Exception):
    """The workbook does not have the expected sheets or columns; nothing can be loaded."""


@dataclass(frozen=True)
class SheetRow:
    number: int  # Excel row number, so a person can find the row in the file
    values: Mapping[str, Any]


@dataclass(frozen=True)
class SheetData:
    name: str
    columns: tuple[str, ...]
    rows: list[SheetRow]


@dataclass(frozen=True)
class RejectedRow:
    sheet: str
    row_number: int
    reason: str


@dataclass
class SheetResult[R: BaseModel]:
    sheet: str
    read: int
    records: list[R] = field(default_factory=list)
    rejected: list[RejectedRow] = field(default_factory=list)


@dataclass
class ParsedCatalog:
    """Valid records of every sheet, in the order they must be written (parents first)."""

    brands: SheetResult[BrandRecord]
    categories: SheetResult[CategoryRecord]
    warehouses: SheetResult[WarehouseRecord]
    products: SheetResult[ProductRecord]
    specifications: SheetResult[SpecificationRecord]
    relations: SheetResult[RelationRecord]
    prices: SheetResult[PriceRecord]
    inventory: SheetResult[InventoryRecord]

    def sheets(self) -> list[SheetResult[Any]]:
        return [
            self.brands,
            self.categories,
            self.warehouses,
            self.products,
            self.specifications,
            self.relations,
            self.prices,
            self.inventory,
        ]


# A check returns the (possibly enriched) record, or the reason to reject the row.
Check = Callable[[Any], Any | str]


def _clean(values: Mapping[str, Any]) -> dict[str, Any]:
    """Drop empty cells so a blank required field is reported as missing."""
    return {
        key: value
        for key, value in values.items()
        if value is not None and not (isinstance(value, str) and not value.strip())
    }


def _describe(error: ValidationError) -> str:
    problems = []
    for item in error.errors():
        location = ".".join(str(part) for part in item["loc"]) or "row"
        message = item["msg"].removeprefix("Value error, ")
        if item["type"] != "missing" and location != "row":
            message = f"{message} (got {str(item['input'])[:60]!r})"
        problems.append(f"{location}: {message}")
    return "; ".join(problems)


def _parse_rows[R: BaseModel](
    sheet: str,
    rows: Sequence[SheetRow],
    model: type[R],
    unique: Mapping[str, Callable[[R], object]],
    check: Check | None = None,
) -> SheetResult[R]:
    result: SheetResult[R] = SheetResult(sheet=sheet, read=len(rows))
    seen: dict[str, dict[object, int]] = {name: {} for name in unique}

    def reject(row: SheetRow, reason: str) -> None:
        result.rejected.append(RejectedRow(sheet, row.number, reason))

    for row in rows:
        try:
            record = model.model_validate(_clean(row.values))
        except ValidationError as error:
            reject(row, _describe(error))
            continue

        checked = check(record) if check else record
        if isinstance(checked, str):
            reject(row, checked)
            continue

        duplicate = next(
            (
                f"duplicate {name} {key(checked)!r} (first seen in row {seen[name][key(checked)]})"
                for name, key in unique.items()
                if key(checked) in seen[name]
            ),
            None,
        )
        if duplicate:
            reject(row, duplicate)
            continue

        for name, key in unique.items():
            seen[name][key(checked)] = row.number
        result.records.append(checked)
    return result


def _unknown(column: str, value: str, known: set[str]) -> str | None:
    return None if value in known else f"unknown {column} {value!r}"


def _category_key(category_name: str, subcategory_name: str) -> tuple[str, str]:
    return (category_name.casefold(), subcategory_name.casefold())


def parse_brands(rows: Sequence[SheetRow]) -> SheetResult[BrandRecord]:
    return _parse_rows("Brands", rows, BrandRecord, {"brand_id": lambda r: r.brand_id})


def parse_categories(rows: Sequence[SheetRow]) -> SheetResult[CategoryRecord]:
    return _parse_rows(
        "Categories",
        rows,
        CategoryRecord,
        {
            "subcategory_id": lambda r: r.subcategory_id,
            "category/subcategory pair": lambda r: _category_key(
                r.category_name, r.subcategory_name
            ),
        },
    )


def parse_warehouses(rows: Sequence[SheetRow]) -> SheetResult[WarehouseRecord]:
    return _parse_rows(
        "Warehouses", rows, WarehouseRecord, {"warehouse_id": lambda r: r.warehouse_id}
    )


def parse_products(
    rows: Sequence[SheetRow], brand_ids: set[str], categories: CategoryIndex
) -> SheetResult[ProductRecord]:
    def check(record: ProductRecord) -> ProductRecord | str:
        if problem := _unknown("brand_id", record.brand_id, brand_ids):
            return problem
        key = _category_key(record.category_name, record.subcategory_name)
        if key not in categories:
            return f"unknown category {record.category_name} / {record.subcategory_name}"
        return record.model_copy(update={"subcategory_id": categories[key]})

    return _parse_rows(
        "Products",
        rows,
        ProductRecord,
        {"product_id": lambda r: r.product_id, "sku": lambda r: r.sku},
        check,
    )


def parse_specifications(
    rows: Sequence[SheetRow], product_ids: set[str]
) -> SheetResult[SpecificationRecord]:
    return _parse_rows(
        "Specifications",
        rows,
        SpecificationRecord,
        {
            "attribute": lambda r: (r.product_id, r.attribute_group, r.attribute_name),
        },
        lambda r: _unknown("product_id", r.product_id, product_ids) or r,
    )


def parse_relations(
    rows: Sequence[SheetRow], product_ids: set[str]
) -> SheetResult[RelationRecord]:
    return _parse_rows(
        "Relations",
        rows,
        RelationRecord,
        {"relation": lambda r: (r.product_id, r.related_product_id, r.relation_type)},
        lambda r: _unknown("product_id", r.product_id, product_ids)
        or _unknown("related_product_id", r.related_product_id, product_ids)
        or r,
    )


def parse_prices(rows: Sequence[SheetRow], product_ids: set[str]) -> SheetResult[PriceRecord]:
    return _parse_rows(
        "Pricing",
        rows,
        PriceRecord,
        {"product_id": lambda r: r.product_id},
        lambda r: _unknown("product_id", r.product_id, product_ids) or r,
    )


def parse_inventory(
    rows: Sequence[SheetRow], product_ids: set[str], warehouse_ids: set[str]
) -> SheetResult[InventoryRecord]:
    return _parse_rows(
        "Inventory",
        rows,
        InventoryRecord,
        {"product/warehouse": lambda r: (r.product_id, r.warehouse_id)},
        lambda r: _unknown("product_id", r.product_id, product_ids)
        or _unknown("warehouse_id", r.warehouse_id, warehouse_ids)
        or r,
    )


def check_structure(sheets: Mapping[str, SheetData]) -> None:
    problems = []
    for name, columns in SHEET_COLUMNS.items():
        if name not in sheets:
            problems.append(f"missing sheet {name!r}")
            continue
        missing = [column for column in columns if column not in sheets[name].columns]
        if missing:
            problems.append(f"sheet {name!r} is missing columns: {', '.join(missing)}")
    if problems:
        raise DatasetStructureError("; ".join(problems))


def _ids(records: Iterable[Any], attribute: str) -> set[str]:
    return {getattr(record, attribute) for record in records}


def parse_catalog(sheets: Mapping[str, SheetData]) -> ParsedCatalog:
    """Validate every sheet, parents first, so children only reference valid parents."""
    check_structure(sheets)

    def rows(name: str) -> list[SheetRow]:
        return sheets[name].rows

    brands = parse_brands(rows("Brands"))
    categories = parse_categories(rows("Categories"))
    warehouses = parse_warehouses(rows("Warehouses"))
    category_index = {
        _category_key(c.category_name, c.subcategory_name): c.subcategory_id
        for c in categories.records
    }
    products = parse_products(
        rows("Products"), _ids(brands.records, "brand_id"), category_index
    )
    product_ids = _ids(products.records, "product_id")
    return ParsedCatalog(
        brands=brands,
        categories=categories,
        warehouses=warehouses,
        products=products,
        specifications=parse_specifications(rows("Specifications"), product_ids),
        relations=parse_relations(rows("Relations"), product_ids),
        prices=parse_prices(rows("Pricing"), product_ids),
        inventory=parse_inventory(
            rows("Inventory"), product_ids, _ids(warehouses.records, "warehouse_id")
        ),
    )
