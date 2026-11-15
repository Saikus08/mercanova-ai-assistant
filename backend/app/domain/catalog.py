"""Catalog entities and rules. Pure Python: no framework or persistence imports."""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal

SortOrder = Literal["price_asc", "price_desc", "rating"]

MIN_COMPARED_PRODUCTS = 2
MAX_COMPARED_PRODUCTS = 4


class ProductNotFound(Exception):
    def __init__(self, product_id: str) -> None:
        super().__init__(f"Product not found: {product_id}")
        self.product_id = product_id


class InvalidComparison(Exception):
    """The ids to compare are fewer than 2 or more than 4."""


def format_number(value: Decimal) -> str:
    """Render a number without trailing zeros: 24.0000 -> "24", 6.7400 -> "6.74"."""
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


@dataclass(frozen=True)
class Specification:
    group: str
    name: str
    value_text: str | None
    value_number: Decimal | None
    unit: str | None

    @property
    def value(self) -> str | None:
        if self.value_text is not None:
            return self.value_text
        if self.value_number is not None:
            return format_number(self.value_number)
        return None


@dataclass(frozen=True)
class Price:
    current: Decimal
    list: Decimal
    discount_percent: Decimal
    currency: str


@dataclass(frozen=True)
class ProductSummary:
    product_id: str
    sku: str
    name: str
    brand: str
    category: str
    subcategory: str
    short_description: str | None
    image_url: str | None
    rating: Decimal | None
    review_count: int | None
    price: Price | None
    available_qty: int

    @property
    def in_stock(self) -> bool:
        return self.available_qty > 0


@dataclass(frozen=True)
class Availability:
    warehouse_id: str
    warehouse_name: str
    city: str | None
    available_qty: int
    pickup_enabled: bool


@dataclass(frozen=True)
class RelatedProduct:
    product_id: str
    name: str
    relation_type: str
    strength: Decimal


@dataclass(frozen=True)
class ProductDetail:
    summary: ProductSummary
    description: str | None
    recommended_for: list[str]
    not_recommended_for: list[str]
    key_features: list[str]
    tags: list[str]
    color: str | None
    width_cm: Decimal | None
    height_cm: Decimal | None
    depth_cm: Decimal | None
    weight_kg: Decimal | None
    warranty_months: int | None
    return_days: int | None
    specifications: list[Specification] = field(default_factory=list)
    availability: list[Availability] = field(default_factory=list)
    related: list[RelatedProduct] = field(default_factory=list)


@dataclass(frozen=True)
class ProductFilters:
    q: str | None = None
    category: str | None = None
    subcategory: str | None = None
    brand: str | None = None
    min_price: Decimal | None = None
    max_price: Decimal | None = None
    in_stock: bool | None = None


@dataclass(frozen=True)
class ProductPage:
    items: list[ProductSummary]
    page: int
    page_size: int
    total: int


@dataclass(frozen=True)
class CategoryGroup:
    category: str
    subcategories: list[str]


@dataclass(frozen=True)
class Warehouse:
    warehouse_id: str
    warehouse_name: str
    city: str | None
    department: str | None
    country: str | None
    pickup_enabled: bool
    shipping_enabled: bool


@dataclass(frozen=True)
class ComparisonAttribute:
    group: str
    name: str
    unit: str | None
    values: dict[str, str | None]


@dataclass(frozen=True)
class Comparison:
    products: list[ProductSummary]
    attributes: list[ComparisonAttribute]
