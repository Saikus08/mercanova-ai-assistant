"""Read-only catalog tools. Price and stock are read from the repository on every call."""

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.application.agent.tool import Tool, ToolContext, ToolDataUnavailable
from app.application.catalog import compare_products, get_product
from app.application.ports import CatalogRepository, EmbeddingModel, SemanticSearch
from app.application.search import search_products
from app.domain.catalog import (
    MAX_COMPARED_PRODUCTS,
    MIN_COMPARED_PRODUCTS,
    Availability,
    Price,
    ProductNotFound,
    ProductSummary,
)
from app.domain.search import DEFAULT_TOP_K, SearchFilters

MAX_ALTERNATIVES = 5
ALTERNATIVE_RELATION = "alternative_to"


class _Args(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class SearchProductsArgs(_Args):
    query: str = Field(
        min_length=1,
        description=(
            "English text describing what the customer needs, e.g. 'quiet mechanical keyboard "
            "for office work'. Never include price or stock."
        ),
    )
    category: str | None = Field(default=None, description="Exact category name to restrict to")
    subcategory: str | None = Field(default=None, description="Exact subcategory name")
    brand: str | None = Field(default=None, description="Exact brand name")
    min_price: float | None = Field(default=None, ge=0, description="Minimum current price")
    max_price: float | None = Field(default=None, ge=0, description="Maximum current price")
    in_stock_only: bool = Field(default=False, description="Only products with stock available")

    @model_validator(mode="after")
    def _check_price_range(self) -> "SearchProductsArgs":
        if None not in (self.min_price, self.max_price) and self.min_price > self.max_price:
            raise ValueError("min_price must not be greater than max_price")
        return self


class ProductIdArgs(_Args):
    product_id: str = Field(min_length=1, description="Product id, e.g. MN-001")


class CompareProductsArgs(_Args):
    product_ids: list[str] = Field(
        min_length=MIN_COMPARED_PRODUCTS,
        max_length=MAX_COMPARED_PRODUCTS,
        description="Ids of the products to compare, between 2 and 4",
    )


def _money(value: Decimal) -> float:
    return round(float(value), 2)


def _price(price: Price | None) -> dict[str, Any] | None:
    if price is None:
        return None
    return {
        "current": _money(price.current),
        "list": _money(price.list),
        "discount_percent": _money(price.discount_percent),
        "currency": price.currency,
    }


def _card(summary: ProductSummary) -> dict[str, Any]:
    """The one product format every tool uses, with the current price and stock."""
    return {
        "product_id": summary.product_id,
        "name": summary.name,
        "brand": summary.brand,
        "category": summary.category,
        "subcategory": summary.subcategory,
        "short_description": summary.short_description,
        "price": _price(summary.price),
        "available_qty": summary.available_qty,
        "in_stock": summary.in_stock,
    }


def _warehouses(availability: list[Availability]) -> list[dict[str, Any]]:
    return [
        {
            "warehouse_id": a.warehouse_id,
            "warehouse_name": a.warehouse_name,
            "city": a.city,
            "available_qty": a.available_qty,
            "pickup_enabled": a.pickup_enabled,
        }
        for a in availability
    ]


def _summary(catalog: CatalogRepository, product_id: str) -> ProductSummary:
    found = catalog.get_summaries([product_id])
    if not found:
        raise ProductNotFound(product_id)
    return found[0]


def _current(catalog: CatalogRepository, product_ids: list[str]) -> dict[str, ProductSummary]:
    """Current price and stock for the ids, read now; no query when there is nothing to read."""
    if not product_ids:
        return {}
    return {s.product_id: s for s in catalog.get_summaries(product_ids)}


def build_catalog_tools(
    catalog: CatalogRepository,
    embedder: EmbeddingModel,
    searcher: SemanticSearch,
    min_similarity: float,
) -> list[Tool]:
    def search(args: SearchProductsArgs, context: ToolContext) -> dict[str, Any]:
        filters = SearchFilters(
            category=args.category,
            subcategory=args.subcategory,
            brand=args.brand,
            min_price=None if args.min_price is None else Decimal(str(args.min_price)),
            max_price=None if args.max_price is None else Decimal(str(args.max_price)),
            in_stock=True if args.in_stock_only else None,
        )
        hits = search_products(
            embedder, searcher, args.query, filters, DEFAULT_TOP_K, min_score=min_similarity
        )
        current = _current(catalog, [h.product_id for h in hits])
        products = [
            {**_card(current[hit.product_id]), "similarity": round(hit.score, 3)}
            for hit in hits
            if hit.product_id in current
        ]
        if not products:
            return {
                "products": [],
                "count": 0,
                "note": "No catalog product is similar enough. Tell the user the store does "
                "not have it and do not invent products or prices.",
            }
        return {"products": products, "count": len(products)}

    def details(args: ProductIdArgs, context: ToolContext) -> dict[str, Any]:
        detail = get_product(catalog, args.product_id)
        return {
            **_card(detail.summary),
            "description": detail.description,
            "key_features": detail.key_features,
            "recommended_for": detail.recommended_for,
            "not_recommended_for": detail.not_recommended_for,
            "color": detail.color,
            "warranty_months": detail.warranty_months,
            "return_days": detail.return_days,
            "specifications": [
                {"group": s.group, "name": s.name, "value": s.value, "unit": s.unit}
                for s in detail.specifications
            ],
            "warehouses": _warehouses(detail.availability),
        }

    def price(args: ProductIdArgs, context: ToolContext) -> dict[str, Any]:
        found = _summary(catalog, args.product_id)
        if found.price is None:
            raise ToolDataUnavailable("The product has no price")
        return {
            "product_id": found.product_id,
            "name": found.name,
            "price": _price(found.price),
        }

    def stock(args: ProductIdArgs, context: ToolContext) -> dict[str, Any]:
        detail = get_product(catalog, args.product_id)
        return {
            "product_id": detail.summary.product_id,
            "name": detail.summary.name,
            "available_qty": detail.summary.available_qty,
            "in_stock": detail.summary.in_stock,
            "warehouses": _warehouses(detail.availability),
        }

    def compare(args: CompareProductsArgs, context: ToolContext) -> dict[str, Any]:
        comparison = compare_products(catalog, args.product_ids)
        return {
            "products": [_card(p) for p in comparison.products],
            "attributes": [
                {"group": a.group, "name": a.name, "unit": a.unit, "values": a.values}
                for a in comparison.attributes
            ],
        }

    def alternatives(args: ProductIdArgs, context: ToolContext) -> dict[str, Any]:
        detail = get_product(catalog, args.product_id)
        related = [r for r in detail.related if r.relation_type == ALTERNATIVE_RELATION]
        related = related[:MAX_ALTERNATIVES]  # the repository returns the strongest first
        current = _current(catalog, [r.product_id for r in related])
        items = []
        for relation in related:
            if relation.product_id not in current:
                continue
            card = _card(current[relation.product_id])
            items.append(
                {
                    "product_id": card["product_id"],
                    "name": card["name"],
                    "relation_strength": _money(relation.strength),
                    "price": card["price"],
                    "available_qty": card["available_qty"],
                    "in_stock": card["in_stock"],
                }
            )
        payload: dict[str, Any] = {
            "product_id": args.product_id,
            "alternatives": items,
            "count": len(items),
        }
        if not items:
            payload["note"] = (
                "No alternatives are registered for this product. Tell the user and do not "
                "invent alternatives."
            )
        return payload

    return [
        Tool(
            "search_products",
            "Use for: finding catalog products that match a customer need. "
            "Use when: the customer describes what they want or asks for recommendations; write "
            "the query in English and put price limits in the price filters, never in the query. "
            "Returns: up to 5 products with current price, stock and similarity, best first; "
            "an empty list with a note when nothing in the catalog is similar enough.",
            SearchProductsArgs,
            search,
        ),
        Tool(
            "get_product_details",
            "Use for: the full description of one product. "
            "Use when: the customer asks about features, specifications, warranty or "
            "suitability of a product whose id you already know. "
            "Returns: static content, specifications, warehouses, and current price and stock.",
            ProductIdArgs,
            details,
        ),
        Tool(
            "get_price",
            "Use for: the current price of one product. "
            "Use when: the customer asks how much a product costs; never answer a price from "
            "memory or earlier messages. "
            "Returns: current price, list price, discount percent and currency.",
            ProductIdArgs,
            price,
        ),
        Tool(
            "get_stock",
            "Use for: the current availability of one product. "
            "Use when: the customer asks whether a product is available or how many units "
            "there are; never answer stock from memory or earlier messages. "
            "Returns: available quantity, in-stock flag and quantity per warehouse.",
            ProductIdArgs,
            stock,
        ),
        Tool(
            "compare_products",
            "Use for: comparing 2 to 4 products side by side. "
            "Use when: the customer asks which of several known products is better or how they "
            "differ. "
            "Returns: each product with current price and stock, and the specifications aligned "
            "by attribute.",
            CompareProductsArgs,
            compare,
        ),
        Tool(
            "get_alternatives",
            "Use for: similar products that can replace one product. "
            "Use when: the product is out of stock, too expensive or the customer wants other "
            "options. "
            "Returns: up to 5 alternatives, strongest relation first, with current price and "
            "stock; an empty list with a note when none are registered.",
            ProductIdArgs,
            alternatives,
        ),
    ]
