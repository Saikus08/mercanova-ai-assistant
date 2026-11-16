"""Tool permission table (AGENTS.md, "Tool permissions"). Least privilege: the model proposes."""

from enum import StrEnum


class Permission(StrEnum):
    FREE = "free"
    CONFIRMATION = "confirmation"
    FORBIDDEN = "forbidden"


PERMISSIONS: dict[str, Permission] = {
    # Read only.
    "search_products": Permission.FREE,
    "get_product_details": Permission.FREE,
    "get_price": Permission.FREE,
    "get_stock": Permission.FREE,
    "compare_products": Permission.FREE,
    "get_alternatives": Permission.FREE,
    "view_cart": Permission.FREE,
    # Quantity is validated against stock.
    "add_to_cart": Permission.FREE,
    # Only prepares a draft for the purchase window: it creates no order (no stock change, no
    # purchase, no personal data).
    "start_checkout": Permission.FREE,
    # Never tools: only the user, through the UI, confirms or cancels an order (RF-12).
    "confirm_order": Permission.FORBIDDEN,
    "cancel_order": Permission.FORBIDDEN,
}
