"""UI blocks built from a chat turn: tool data stays authoritative, summaries only enrich."""

from decimal import Decimal
from typing import Any

from app.application.agent.answer import TurnResult
from app.application.chat_blocks import build_blocks, product_ids_to_enrich
from app.domain.agent import StopReason
from app.domain.catalog import Price, ProductSummary


def card(product_id: str, price: float = 10.0, qty: int = 5) -> dict[str, Any]:
    return {
        "product_id": product_id,
        "name": f"Name {product_id}",
        "brand": "Brand",
        "category": "Cat",
        "subcategory": "Sub",
        "short_description": "short",
        "price": {"current": price, "list": price, "discount_percent": 0.0, "currency": "USD"},
        "available_qty": qty,
        "in_stock": qty > 0,
    }


def summary(product_id: str, price: str = "99.00", qty: int = 99) -> ProductSummary:
    return ProductSummary(
        product_id=product_id,
        sku=f"SKU-{product_id}",
        name="Stale name",
        brand="Brand",
        category="Cat",
        subcategory="Sub",
        short_description=None,
        image_url=f"https://img/{product_id}.png",
        rating=Decimal("4.5"),
        review_count=12,
        price=Price(Decimal(price), Decimal(price), Decimal("0"), "USD"),
        available_qty=qty,
    )


def tool(name: str, result: dict[str, Any], ok: bool = True) -> dict[str, Any]:
    return {"name": name, "arguments": {}, "ok": ok, "duration_ms": 1, "result": result}


def turn(**overrides: Any) -> TurnResult:
    values: dict[str, Any] = {
        "reply": "ok",
        "recommendations": [],
        "clarification": None,
        "not_found": None,
        "tools_used": [],
        "steps": 1,
        "stop_reason": StopReason.ANSWER,
        "degraded": False,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "trace_id": "t",
    }
    values.update(overrides)
    return TurnResult(**values)


CART = {
    "items": [
        {
            "product_id": "A",
            "name": "Name A",
            "unit_price": 10.0,
            "quantity": 2,
            "line_total": 20.0,
            "available_qty": 5,
        }
    ],
    "item_count": 2,
    "total": 20.0,
    "currency": "USD",
}


def test_plain_reply_has_no_blocks():
    assert build_blocks(turn(), {}) == []
    assert product_ids_to_enrich(turn()) == []


def test_degraded_result_has_no_blocks():
    result = turn(
        degraded=True,
        recommendations=[{"product": card("A"), "reason": "r"}],
        clarification={"question": "q?", "options": ["a", "b"]},
        not_found="x",
    )

    assert build_blocks(result, {"A": summary("A")}) == []


def test_recommendations_are_enriched_but_price_and_stock_stay_from_the_tool():
    result = turn(recommendations=[{"product": card("A", price=10.0, qty=3), "reason": "fits"}])

    blocks = build_blocks(result, {"A": summary("A", price="99.00", qty=99)})

    assert [b["type"] for b in blocks] == ["product_recommendations"]
    item = blocks[0]["items"][0]
    assert item["reason"] == "fits"
    product = item["product"]
    assert product["price"]["current"] == 10.0
    assert product["available_qty"] == 3
    assert product["in_stock"] is True
    assert product["name"] == "Name A"
    assert product["sku"] == "SKU-A"
    assert product["brand"] == "Brand"
    assert product["image_url"] == "https://img/A.png"
    assert product["rating"] == 4.5
    assert isinstance(product["rating"], float)
    assert product["review_count"] == 12


def test_missing_summary_leaves_enrichment_fields_empty():
    result = turn(recommendations=[{"product": card("A"), "reason": "r"}])

    product = build_blocks(result, {})[0]["items"][0]["product"]

    assert product["sku"] is None
    assert product["image_url"] is None
    assert product["rating"] is None
    assert product["review_count"] is None
    assert product["price"]["current"] == 10.0


def test_comparison_uses_the_last_successful_compare_and_enriches_products():
    attributes = [{"group": "g", "name": "n", "unit": None, "values": {"A": "1", "B": "2"}}]
    first = tool("compare_products", {"products": [card("X"), card("Y")], "attributes": []})
    last = tool("compare_products", {"products": [card("A"), card("B")], "attributes": attributes})
    failed = tool("compare_products", {"error": "boom"}, ok=False)
    result = turn(tools_used=[first, last, failed])

    blocks = build_blocks(result, {"A": summary("A")})

    assert [b["type"] for b in blocks] == ["comparison"]
    block = blocks[0]
    assert block["attributes"] == attributes
    assert [p["product_id"] for p in block["products"]] == ["A", "B"]
    assert block["products"][0]["image_url"] == "https://img/A.png"
    assert block["products"][0]["price"]["current"] == 10.0
    assert block["products"][1]["image_url"] is None


def test_failed_compare_alone_yields_no_comparison():
    result = turn(tools_used=[tool("compare_products", {"error": "x"}, ok=False)])

    assert build_blocks(result, {}) == []


def test_clarification_and_not_found_blocks():
    result = turn(clarification={"question": "q?", "options": ["a", "b"]}, not_found="PS9")

    assert build_blocks(result, {}) == [
        {"type": "clarification", "question": "q?", "options": ["a", "b"]},
        {"type": "not_found", "query": "PS9"},
    ]


def test_cart_updated_drops_the_added_key_and_uses_the_last_ok_add():
    older = tool("add_to_cart", {**CART, "added": {"product_id": "A", "quantity": 1}})
    added = {"product_id": "A", "quantity": 1}
    newer = tool("add_to_cart", {**CART, "total": 30.0, "added": added})
    failed = tool("add_to_cart", {"error": "no stock"}, ok=False)

    blocks = build_blocks(turn(tools_used=[older, newer, failed]), {})

    assert blocks == [{"type": "cart_updated", "cart": {**CART, "total": 30.0}}]


def test_checkout_draft_only_when_ready():
    ready = tool("start_checkout", {"ready": True, "cart": CART, "problems": []})
    not_ready = tool("start_checkout", {"ready": False, "cart": CART, "problems": [{}]})

    assert build_blocks(turn(tools_used=[ready]), {}) == [
        {"type": "checkout_draft", "cart": CART}
    ]
    assert build_blocks(turn(tools_used=[not_ready]), {}) == []


def test_blocks_come_in_a_fixed_order():
    result = turn(
        recommendations=[{"product": card("A"), "reason": "r"}],
        clarification={"question": "q?", "options": ["a", "b"]},
        not_found="x",
        tools_used=[
            tool("start_checkout", {"ready": True, "cart": CART, "problems": []}),
            tool("add_to_cart", {**CART, "added": {}}),
            tool("compare_products", {"products": [card("B")], "attributes": []}),
        ],
    )

    types = [b["type"] for b in build_blocks(result, {})]

    assert types == [
        "comparison",
        "product_recommendations",
        "clarification",
        "not_found",
        "cart_updated",
        "checkout_draft",
    ]


def test_product_ids_to_enrich_are_ordered_and_unique():
    result = turn(
        recommendations=[
            {"product": card("B"), "reason": "r"},
            {"product": card("A"), "reason": "r"},
        ],
        tools_used=[
            tool("compare_products", {"products": [card("A"), card("C")], "attributes": []}),
            tool("compare_products", {"error": "x"}, ok=False),
        ],
    )

    assert product_ids_to_enrich(result) == ["B", "A", "C"]
