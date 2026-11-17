"""UI blocks of a chat turn, built only from the tool results and the final answer.

Price, stock and name always stay as the tools returned them in the current turn. The catalog
summaries only add presentation fields (sku, image, rating) that the tool cards do not carry.
"""

from typing import Any

from app.application.agent.answer import TurnResult
from app.domain.catalog import ProductSummary


def _last_ok(result: TurnResult, tool_name: str) -> dict[str, Any] | None:
    for use in reversed(result.tools_used):
        if use["name"] == tool_name and use["ok"]:
            return use["result"]
    return None


def _enrich(card: dict[str, Any], summaries: dict[str, ProductSummary]) -> dict[str, Any]:
    found = summaries.get(card["product_id"])
    rating = None if found is None or found.rating is None else float(found.rating)
    return {
        **card,
        "sku": None if found is None else found.sku,
        "image_url": None if found is None else found.image_url,
        "rating": rating,
        "review_count": None if found is None else found.review_count,
    }


def product_ids_to_enrich(result: TurnResult) -> list[str]:
    """Ordered unique ids of the products shown as cards or in a comparison."""
    ids = [r["product"]["product_id"] for r in result.recommendations]
    compared = _last_ok(result, "compare_products")
    if compared is not None:
        ids.extend(p["product_id"] for p in compared["products"])
    return list(dict.fromkeys(ids))


def build_blocks(result: TurnResult, summaries: dict[str, ProductSummary]) -> list[dict[str, Any]]:
    if result.degraded:
        return []
    blocks: list[dict[str, Any]] = []

    compared = _last_ok(result, "compare_products")
    if compared is not None:
        blocks.append(
            {
                "type": "comparison",
                "products": [_enrich(p, summaries) for p in compared["products"]],
                "attributes": compared["attributes"],
            }
        )
    if result.recommendations:
        items = [
            {"product": _enrich(r["product"], summaries), "reason": r["reason"]}
            for r in result.recommendations
        ]
        blocks.append({"type": "product_recommendations", "items": items})
    if result.clarification is not None:
        blocks.append(
            {
                "type": "clarification",
                "question": result.clarification["question"],
                "options": result.clarification["options"],
            }
        )
    if result.not_found:
        blocks.append({"type": "not_found", "query": result.not_found})

    added = _last_ok(result, "add_to_cart")
    if added is not None:
        cart = {key: value for key, value in added.items() if key != "added"}
        blocks.append({"type": "cart_updated", "cart": cart})

    checkout = _last_ok(result, "start_checkout")
    if checkout is not None and checkout.get("ready"):
        blocks.append({"type": "checkout_draft", "cart": checkout["cart"]})
    return blocks
