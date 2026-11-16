"""Read-only catalog tools with fake repositories (no database, no LLM)."""

import json
import re
from decimal import Decimal

import pytest

from app.application.agent.catalog_tools import build_catalog_tools
from app.application.agent.dispatcher import ToolDispatcher
from app.application.agent.permissions import PERMISSIONS, Permission
from app.application.agent.registry import ToolRegistry
from app.application.agent.tool import ToolContext
from app.domain.catalog import (
    Availability,
    Price,
    ProductDetail,
    ProductSummary,
    RelatedProduct,
    Specification,
)
from app.domain.search import DEFAULT_TOP_K, SearchFilters, SearchHit

CONTEXT = ToolContext(session_id="s1")


def summary(product_id="MN-001", price="100.00", qty=8, **overrides) -> ProductSummary:
    values = {
        "product_id": product_id,
        "sku": f"SKU-{product_id}",
        "name": f"Name {product_id}",
        "brand": "Flux",
        "category": "Monitors",
        "subcategory": "Gaming",
        "short_description": "Short text",
        "image_url": None,
        "rating": None,
        "review_count": None,
        "price": None
        if price is None
        else Price(Decimal(price), Decimal("120.00"), Decimal("16.67"), "USD"),
        "available_qty": qty,
    }
    return ProductSummary(**{**values, **overrides})


def detail(product_id="MN-001", related=(), **summary_overrides) -> ProductDetail:
    return ProductDetail(
        summary=summary(product_id, **summary_overrides),
        description="Long text",
        recommended_for=["gaming"],
        not_recommended_for=["printing"],
        key_features=["QHD"],
        tags=["monitor"],
        color="Black",
        width_cm=None,
        height_cm=None,
        depth_cm=None,
        weight_kg=None,
        warranty_months=12,
        return_days=30,
        specifications=[Specification("Display", "Size", None, Decimal("24.0"), "in")],
        availability=[Availability("W1", "Centro", "Montevideo", 5, True)],
        related=list(related),
    )


class FakeCatalog:
    def __init__(self, summaries=(), details=()) -> None:
        self.summaries = {s.product_id: s for s in summaries}
        self.details = {d.summary.product_id: d for d in details}
        self.summary_calls: list[list[str]] = []

    def get_summaries(self, product_ids):
        self.summary_calls.append(list(product_ids))
        return [self.summaries[i] for i in product_ids if i in self.summaries]

    def get_detail(self, product_id):
        return self.details.get(product_id)

    def get_specifications(self, product_ids):
        return {
            "MN-001": [Specification("Display", "Size", None, Decimal("24"), "in")],
            "MN-002": [Specification("Display", "Size", None, Decimal("27.5"), "in")],
        }


class FakeEmbedder:
    index_id = "fake+v1"

    def embed_query(self, text):
        return [1.0, 0.0]


class FakeSearcher:
    def __init__(self, hits=()) -> None:
        self.hits = list(hits)
        self.calls: list[tuple[SearchFilters, int]] = []

    def search(self, vector, filters, top_k, index_id):
        self.calls.append((filters, top_k))
        return self.hits


def make_dispatcher(catalog=None, hits=(), min_similarity=0.62):
    catalog = catalog or FakeCatalog()
    searcher = FakeSearcher(hits)
    tools = build_catalog_tools(catalog, FakeEmbedder(), searcher, min_similarity)
    return ToolDispatcher(ToolRegistry(tools)), catalog, searcher


# --- registry-wide rules -------------------------------------------------------------------


def all_tools():
    return build_catalog_tools(FakeCatalog(), FakeEmbedder(), FakeSearcher(), 0.62)


def test_catalog_tools_cover_the_six_read_only_names():
    assert [tool.name for tool in all_tools()] == [
        "search_products",
        "get_product_details",
        "get_price",
        "get_stock",
        "compare_products",
        "get_alternatives",
    ]


def test_every_description_has_use_for_use_when_and_returns_parts():
    for tool in all_tools():
        for marker in ("Use for:", "Use when:", "Returns:"):
            assert marker in tool.description, f"{tool.name} lacks {marker}"


def test_every_tool_name_is_snake_case_and_has_a_free_permission():
    for tool in all_tools():
        assert re.fullmatch(r"[a-z]+(_[a-z]+)*", tool.name)
        assert PERMISSIONS[tool.name] is Permission.FREE


def test_every_argument_has_a_description_in_its_schema():
    for tool in all_tools():
        for name, prop in tool.parameters_schema()["properties"].items():
            assert prop.get("description"), f"{tool.name}.{name} has no description"


def test_registry_accepts_all_catalog_tools():
    assert len(ToolRegistry(all_tools()).names()) == 6


# --- search_products -----------------------------------------------------------------------


def hit(product_id, score):
    return SearchHit(product_id, f"Indexed {product_id}", score, "indexed text")


def test_search_returns_current_price_and_stock_in_search_order():
    catalog = FakeCatalog([summary("MN-001", "100.00", 8), summary("MN-002", "55.5", 0)])
    dispatcher, _, searcher = make_dispatcher(catalog, [hit("MN-002", 0.8), hit("MN-001", 0.7)])

    result = dispatcher.dispatch("search_products", {"query": "  gaming monitor "}, CONTEXT)

    assert result.ok is True
    assert result.payload["count"] == 2
    first, second = result.payload["products"]
    assert [first["product_id"], second["product_id"]] == ["MN-002", "MN-001"]
    assert first["price"] == {
        "current": 55.5,
        "list": 120.0,
        "discount_percent": 16.67,
        "currency": "USD",
    }
    assert (first["available_qty"], first["in_stock"]) == (0, False)
    assert (second["available_qty"], second["in_stock"]) == (8, True)
    assert second["similarity"] == 0.7
    assert second["name"] == "Name MN-001"  # current catalog data, not the indexed text
    assert searcher.calls[0][1] == DEFAULT_TOP_K
    json.dumps(result.payload)


def test_search_returns_a_note_and_no_products_when_nothing_passes_the_threshold():
    dispatcher, catalog, _ = make_dispatcher(hits=[hit("MN-001", 0.5)])

    result = dispatcher.dispatch("search_products", {"query": "cheese"}, CONTEXT)

    assert result.ok is True
    assert result.payload["products"] == []
    assert result.payload["count"] == 0
    assert "do not invent products or prices" in result.payload["note"]
    assert catalog.summary_calls == []


def test_search_maps_filters_to_the_search_use_case():
    dispatcher, _, searcher = make_dispatcher()

    dispatcher.dispatch(
        "search_products",
        {
            "query": "monitor",
            "category": "Monitors",
            "subcategory": "Gaming",
            "brand": "Flux",
            "min_price": 10,
            "max_price": 99.5,
            "in_stock_only": True,
        },
        CONTEXT,
    )

    assert searcher.calls[0][0] == SearchFilters(
        "Monitors", "Gaming", "Flux", Decimal("10"), Decimal("99.5"), True
    )


def test_search_leaves_stock_filter_unset_when_in_stock_only_is_false():
    dispatcher, _, searcher = make_dispatcher()

    dispatcher.dispatch("search_products", {"query": "monitor"}, CONTEXT)

    assert searcher.calls[0][0].in_stock is None


def test_search_rejects_min_price_above_max_price():
    dispatcher, _, searcher = make_dispatcher()

    result = dispatcher.dispatch(
        "search_products", {"query": "monitor", "min_price": 50, "max_price": 10}, CONTEXT
    )

    assert result.ok is False
    assert "min_price" in result.payload["error"]
    assert searcher.calls == []


@pytest.mark.parametrize(
    "arguments", [{"query": ""}, {"query": "   "}, {"query": "a", "min_price": -1}]
)
def test_search_rejects_invalid_arguments(arguments):
    dispatcher, _, searcher = make_dispatcher()

    assert dispatcher.dispatch("search_products", arguments, CONTEXT).ok is False
    assert searcher.calls == []


def test_search_skips_a_hit_whose_product_vanished_before_the_price_read():
    catalog = FakeCatalog([summary("MN-001")])
    dispatcher, _, _ = make_dispatcher(catalog, [hit("MN-009", 0.9), hit("MN-001", 0.8)])

    result = dispatcher.dispatch("search_products", {"query": "monitor"}, CONTEXT)

    assert [p["product_id"] for p in result.payload["products"]] == ["MN-001"]
    assert result.payload["count"] == 1


# --- details, price, stock -----------------------------------------------------------------


def test_product_details_return_static_content_price_stock_and_warehouses():
    dispatcher, _, _ = make_dispatcher(FakeCatalog(details=[detail()]))

    result = dispatcher.dispatch("get_product_details", {"product_id": "MN-001"}, CONTEXT)

    payload = result.payload
    assert result.ok is True
    assert payload["description"] == "Long text"
    assert payload["key_features"] == ["QHD"]
    assert payload["recommended_for"] == ["gaming"]
    assert payload["not_recommended_for"] == ["printing"]
    assert payload["warranty_months"] == 12
    assert payload["price"]["current"] == 100.0
    assert payload["specifications"] == [
        {"group": "Display", "name": "Size", "value": "24", "unit": "in"}
    ]
    assert payload["warehouses"] == [
        {
            "warehouse_id": "W1",
            "warehouse_name": "Centro",
            "city": "Montevideo",
            "available_qty": 5,
            "pickup_enabled": True,
        }
    ]
    json.dumps(payload)


@pytest.mark.parametrize(
    ("tool", "arguments"),
    [
        ("get_product_details", {"product_id": "NOPE"}),
        ("get_price", {"product_id": "NOPE"}),
        ("get_stock", {"product_id": "NOPE"}),
        ("get_alternatives", {"product_id": "NOPE"}),
        ("compare_products", {"product_ids": ["NOPE", "MN-001"]}),
    ],
)
def test_tools_return_an_actionable_error_when_the_product_does_not_exist(tool, arguments):
    catalog = FakeCatalog([summary("MN-001")], [detail()])
    dispatcher, _, _ = make_dispatcher(catalog)

    result = dispatcher.dispatch(tool, arguments, CONTEXT)

    assert result.ok is False
    assert "NOPE" in result.payload["error"]
    assert "search_products" in result.payload["hint"]


def test_get_price_returns_the_current_price_block():
    dispatcher, _, _ = make_dispatcher(FakeCatalog([summary("MN-001", "99.999")]))

    result = dispatcher.dispatch("get_price", {"product_id": "MN-001"}, CONTEXT)

    assert result.payload == {
        "product_id": "MN-001",
        "name": "Name MN-001",
        "price": {"current": 100.0, "list": 120.0, "discount_percent": 16.67, "currency": "USD"},
    }


def test_get_price_fails_with_a_data_unavailable_hint_when_there_is_no_price_row():
    dispatcher, _, _ = make_dispatcher(FakeCatalog([summary("MN-001", price=None)]))

    result = dispatcher.dispatch("get_price", {"product_id": "MN-001"}, CONTEXT)

    assert result.ok is False
    assert result.payload["error"] == "The product has no price"
    assert "not available" in result.payload["hint"]


def test_get_stock_returns_quantity_and_warehouses():
    dispatcher, _, _ = make_dispatcher(FakeCatalog(details=[detail(qty=0)]))

    result = dispatcher.dispatch("get_stock", {"product_id": "MN-001"}, CONTEXT)

    assert result.payload["available_qty"] == 0
    assert result.payload["in_stock"] is False
    assert result.payload["warehouses"][0]["warehouse_id"] == "W1"


# --- compare and alternatives --------------------------------------------------------------


def test_compare_returns_products_with_price_and_aligned_attributes():
    catalog = FakeCatalog([summary("MN-001"), summary("MN-002", "200.00", 0)])
    dispatcher, _, _ = make_dispatcher(catalog)

    result = dispatcher.dispatch(
        "compare_products", {"product_ids": ["MN-001", "MN-002"]}, CONTEXT
    )

    assert result.ok is True
    assert [p["product_id"] for p in result.payload["products"]] == ["MN-001", "MN-002"]
    assert result.payload["products"][1]["price"]["current"] == 200.0
    assert result.payload["products"][1]["available_qty"] == 0
    assert result.payload["attributes"] == [
        {
            "group": "Display",
            "name": "Size",
            "unit": "in",
            "values": {"MN-001": "24", "MN-002": "27.5"},
        }
    ]


@pytest.mark.parametrize("ids", [["MN-001"], ["a", "b", "c", "d", "e"], []])
def test_compare_rejects_a_wrong_number_of_products(ids):
    dispatcher, _, _ = make_dispatcher()

    assert dispatcher.dispatch("compare_products", {"product_ids": ids}, CONTEXT).ok is False


def test_compare_reports_invalid_comparison_when_the_ids_are_repeated():
    dispatcher, _, _ = make_dispatcher(FakeCatalog([summary("MN-001")]))

    result = dispatcher.dispatch(
        "compare_products", {"product_ids": ["MN-001", "MN-001"]}, CONTEXT
    )

    assert result.ok is False
    assert "between 2 and 4 different products" in result.payload["hint"]


def related(product_id, relation_type, strength):
    return RelatedProduct(product_id, f"Name {product_id}", relation_type, Decimal(strength))


def test_alternatives_keep_only_alternative_to_relations_with_current_price_and_stock():
    catalog = FakeCatalog(
        [summary("MN-002", "200.00", 3), summary("MN-003", "90.00", 0), summary("MN-004")],
        [
            detail(
                related=[
                    related("MN-003", "alternative_to", "0.90"),
                    related("MN-004", "accessory_for", "0.80"),
                    related("MN-002", "alternative_to", "0.70"),
                ]
            )
        ],
    )
    dispatcher, _, _ = make_dispatcher(catalog)

    result = dispatcher.dispatch("get_alternatives", {"product_id": "MN-001"}, CONTEXT)

    assert result.payload["product_id"] == "MN-001"
    assert result.payload["count"] == 2
    assert result.payload["alternatives"] == [
        {
            "product_id": "MN-003",
            "name": "Name MN-003",
            "relation_strength": 0.9,
            "price": {
                "current": 90.0,
                "list": 120.0,
                "discount_percent": 16.67,
                "currency": "USD",
            },
            "available_qty": 0,
            "in_stock": False,
        },
        {
            "product_id": "MN-002",
            "name": "Name MN-002",
            "relation_strength": 0.7,
            "price": {
                "current": 200.0,
                "list": 120.0,
                "discount_percent": 16.67,
                "currency": "USD",
            },
            "available_qty": 3,
            "in_stock": True,
        },
    ]


def test_alternatives_are_capped_at_five():
    rows = [related(f"MN-1{i}", "alternative_to", "0.5") for i in range(7)]
    catalog = FakeCatalog([summary(r.product_id) for r in rows], [detail(related=rows)])
    dispatcher, _, _ = make_dispatcher(catalog)

    result = dispatcher.dispatch("get_alternatives", {"product_id": "MN-001"}, CONTEXT)

    assert result.payload["count"] == 5


def test_alternatives_return_an_empty_list_with_a_note_when_there_are_none():
    dispatcher, _, _ = make_dispatcher(FakeCatalog(details=[detail()]))

    result = dispatcher.dispatch("get_alternatives", {"product_id": "MN-001"}, CONTEXT)

    assert result.ok is True
    assert result.payload["alternatives"] == []
    assert result.payload["count"] == 0
    assert "do not invent" in result.payload["note"]
