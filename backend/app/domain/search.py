"""Semantic search entities and rules. Pure Python: no framework or persistence imports."""

from dataclasses import dataclass
from decimal import Decimal

DEFAULT_TOP_K = 5
MAX_TOP_K = 5
MIN_TOP_K = 1


class SearchUnavailable(Exception):
    """The embedding model or the search backend cannot answer right now."""


@dataclass(frozen=True)
class SearchFilters:
    category: str | None = None
    subcategory: str | None = None
    brand: str | None = None
    min_price: Decimal | None = None
    max_price: Decimal | None = None
    in_stock: bool | None = None


@dataclass(frozen=True)
class SearchHit:
    """A matching product. Price and stock are intentionally absent: tools read them later."""

    product_id: str
    name: str
    score: float  # cosine similarity, 0..1
    short_description: str | None


@dataclass(frozen=True)
class ProductDocumentSource:
    """Static product content that goes into the index. Never price, stock or rating."""

    product_id: str
    name: str
    brand: str
    category: str
    subcategory: str
    short_description: str | None
    description: str | None
    key_features: list[str]
    recommended_for: list[str]
    not_recommended_for: list[str]
    tags: list[str]


def build_product_document(product: ProductDocumentSource) -> str:
    """Text embedded for a product: labelled lines in a fixed order, empty fields skipped."""
    fields = [
        ("Name", product.name),
        ("Brand", product.brand),
        ("Category", product.category),
        ("Subcategory", product.subcategory),
        ("Short description", product.short_description),
        ("Description", product.description),
        ("Key features", _join(product.key_features)),
        ("Recommended for", _join(product.recommended_for)),
        ("Not recommended for", _join(product.not_recommended_for)),
        ("Tags", _join(product.tags)),
    ]
    return "\n".join(
        f"{label}: {value.strip()}" for label, value in fields if value and value.strip()
    )


def _join(values: list[str]) -> str:
    return ", ".join(v.strip() for v in values if v and v.strip())
