"""Validated records built from the course dataset, one model per sheet.

Field names match the ORM columns, so ``record.model_dump()`` is ready to insert.
Lengths and numeric scales mirror the column types: a row that would not fit the
table is rejected here instead of aborting the whole load in the database.
"""

from collections.abc import Callable
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated, Any

from pydantic import (
    AfterValidator,
    AliasChoices,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)


def _split_list(value: object) -> object:
    """Turn ``"a; b ;;c"`` into ``["a", "b", "c"]``; a missing value becomes an empty list."""
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(";") if item.strip()]
    return value


def _float_to_text(value: object) -> object:
    # Excel numbers arrive as floats; their shortest text form keeps 4.3 as 4.3, not 4.2999...
    return repr(value) if isinstance(value, float) else value


def _fit_column(scale: int, precision: int) -> Callable[[Decimal], Decimal]:
    """Round to the column scale and reject values that do not fit NUMERIC(precision, scale)."""
    exponent = Decimal(1).scaleb(-scale)
    limit = Decimal(10) ** (precision - scale)

    def fit(value: Decimal) -> Decimal:
        rounded = value.quantize(exponent, rounding=ROUND_HALF_UP)
        if abs(rounded) >= limit:
            raise ValueError(f"must be less than {limit}")
        return rounded

    return fit


def _assume_utc(value: datetime) -> datetime:
    # The dataset has no time zone; its timestamps are stored as UTC.
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _numeric(scale: int, precision: int, **bounds: int) -> Any:
    """Decimal type for a NUMERIC(precision, scale) column, with optional ge/le bounds."""
    return Annotated[
        Decimal,
        Field(**bounds),
        BeforeValidator(_float_to_text),
        AfterValidator(_fit_column(scale, precision)),
    ]


def _code(max_length: int) -> Any:
    return Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=max_length)
    ]


Code16 = _code(16)
Code32 = _code(32)
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
TextList = Annotated[list[Text], BeforeValidator(_split_list)]
CurrencyCode = Annotated[
    str, StringConstraints(strip_whitespace=True, to_upper=True, pattern=r"^[A-Z]{3}$")
]
NonNegativeInt = Annotated[int, Field(ge=0)]
Timestamp = Annotated[datetime, AfterValidator(_assume_utc)]
Money = _numeric(2, 10, ge=0)
Size = _numeric(2, 8, ge=0)
Weight = _numeric(3, 8, ge=0)
Rating = _numeric(2, 3, ge=0, le=5)
Strength = _numeric(3, 4, ge=0, le=1)
Percent = _numeric(2, 5, ge=0, le=100)
SpecNumber = _numeric(4, 14)


class DatasetRecord(BaseModel):
    model_config = ConfigDict(
        extra="ignore", frozen=True, populate_by_name=True, coerce_numbers_to_str=True
    )


class BrandRecord(DatasetRecord):
    brand_id: Code16
    brand_name: Text
    country_of_origin: Text | None = None
    positioning: Text | None = None


class CategoryRecord(DatasetRecord):
    subcategory_id: Code16
    subcategory_name: Text
    category_id: Code16
    category_name: Text
    department: Text | None = None
    sort_order: int | None = None


class WarehouseRecord(DatasetRecord):
    warehouse_id: Code16
    warehouse_name: Text
    city: Text | None = None
    department: Text | None = None
    country: Text | None = None
    pickup_enabled: bool = True
    shipping_enabled: bool = True


class ProductRecord(DatasetRecord):
    product_id: Code32
    sku: Code32
    name: Text
    brand_id: Code16
    # The Products sheet names the category instead of referencing its id.
    category_name: Text = Field(validation_alias=AliasChoices("category", "category_name"))
    subcategory_name: Text = Field(
        validation_alias=AliasChoices("subcategory", "subcategory_name")
    )
    # Not in the sheet: the parser resolves it from (category_name, subcategory_name).
    subcategory_id: Code16 | None = None
    short_description: Text | None = None
    description: Text | None = None
    recommended_for: TextList = []
    not_recommended_for: TextList = []
    key_features: TextList = []
    tags: TextList = []
    color: Text | None = None
    weight_kg: Weight | None = None
    width_cm: Size | None = None
    height_cm: Size | None = None
    depth_cm: Size | None = None
    warranty_months: NonNegativeInt | None = None
    return_days: NonNegativeInt | None = None
    rating: Rating | None = None
    review_count: NonNegativeInt | None = None
    launch_date: date | None = None
    active: bool = True
    image_url: Text | None = None


class SpecificationRecord(DatasetRecord):
    product_id: Code32
    attribute_group: Text
    attribute_name: Text
    value_text: Text | None = None
    value_number: SpecNumber | None = None
    unit: Text | None = None

    @model_validator(mode="after")
    def _has_value(self) -> "SpecificationRecord":
        if self.value_text is None and self.value_number is None:
            raise ValueError("needs value_text or value_number")
        return self


class RelationRecord(DatasetRecord):
    product_id: Code32
    related_product_id: Code32
    relation_type: Code32
    strength: Strength

    @model_validator(mode="after")
    def _not_self_related(self) -> "RelationRecord":
        if self.product_id == self.related_product_id:
            raise ValueError("a product cannot be related to itself")
        return self


class PriceRecord(DatasetRecord):
    product_id: Code32
    currency: CurrencyCode
    list_price: Money
    current_price: Money
    discount_percent: Percent = Decimal("0")
    tax_included: bool = True
    price_updated_at: Timestamp | None = None


class InventoryRecord(DatasetRecord):
    product_id: Code32
    warehouse_id: Code16
    on_hand_qty: NonNegativeInt
    reserved_qty: NonNegativeInt = 0
    available_qty: NonNegativeInt
    inventory_status: Text | None = None
    inventory_updated_at: Timestamp | None = None
