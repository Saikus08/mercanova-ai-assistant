"""Cart tools and checkout preparation. The session comes from the harness, never the model."""

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.application.agent.tool import Tool, ToolContext
from app.application.cart import add_item, view_cart
from app.application.ports import CartRepository
from app.domain.cart import MAX_QUANTITY_PER_LINE, Cart
from app.domain.purchase import CartEmpty

READY_NEXT_STEP = (
    "Tell the user that the purchase window is ready. The user must enter their details and "
    "press the confirm button in the interface; you cannot confirm or cancel orders."
)
PROBLEMS_NEXT_STEP = (
    "Explain each problem to the user: the requested quantity is higher than the current stock. "
    "Ask the user to adjust the quantity in the cart, then call start_checkout again."
)


class _Args(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class NoArgs(_Args):
    pass


class StartCheckoutArgs(_Args):
    """No fields on purpose: customer data never passes through the model."""


class AddToCartArgs(_Args):
    product_id: str = Field(min_length=1, description="Product id, e.g. MN-001")
    quantity: int = Field(
        default=1,
        description=(
            f"Units to add, a whole number from 1 to {MAX_QUANTITY_PER_LINE}. "
            "Added to what the cart already holds."
        ),
    )


def _money(value: Decimal) -> float:
    return round(float(value), 2)


def _cart(cart: Cart) -> dict[str, Any]:
    """The one cart format every cart tool uses, with current prices and stock."""
    return {
        "items": [
            {
                "product_id": line.product_id,
                "name": line.name,
                "unit_price": _money(line.unit_price),
                "quantity": line.quantity,
                "line_total": _money(line.line_total),
                "available_qty": line.available_qty,
            }
            for line in cart.items
        ],
        "item_count": cart.item_count,
        "total": _money(cart.total),
        "currency": cart.currency,
    }


def build_cart_tools(cart: CartRepository) -> list[Tool]:
    def view(args: NoArgs, context: ToolContext) -> dict[str, Any]:
        return _cart(view_cart(cart, context.session_id))

    def add(args: AddToCartArgs, context: ToolContext) -> dict[str, Any]:
        updated = add_item(cart, context.session_id, args.product_id, args.quantity)
        return {
            **_cart(updated),
            "added": {"product_id": args.product_id, "quantity": args.quantity},
        }

    def checkout(args: StartCheckoutArgs, context: ToolContext) -> dict[str, Any]:
        current = view_cart(cart, context.session_id)
        if not current.items:
            raise CartEmpty
        problems = [
            {
                "product_id": line.product_id,
                "name": line.name,
                "requested": line.quantity,
                "available": line.available_qty,
            }
            for line in current.items
            if line.quantity > line.available_qty
        ]
        return {
            "ready": not problems,
            "cart": _cart(current),
            "problems": problems,
            "next_step": PROBLEMS_NEXT_STEP if problems else READY_NEXT_STEP,
        }

    return [
        Tool(
            "view_cart",
            "Use for: reading the current cart of the customer. "
            "Use when: the customer asks what is in the cart or its total, or before "
            "talking about quantities; never answer cart contents or prices from memory. "
            "Returns: items with current unit price, quantity, line total and available stock, "
            "item count, total and currency; an empty list and a total of 0 when the cart is "
            "empty.",
            NoArgs,
            view,
        ),
        Tool(
            "add_to_cart",
            "Use for: adding units of one product to the cart. "
            "Use when: the customer clearly asks to add or buy a product whose id you already "
            "know; the quantity is checked against the current stock. "
            "Returns: what was added and the updated cart; an error with a hint when the "
            "product is unknown, not for sale or has not enough stock.",
            AddToCartArgs,
            add,
        ),
        Tool(
            "start_checkout",
            "Use for: preparing the purchase window of the interface from the current cart. "
            "Use when: the customer wants to pay or finish the purchase. It never creates an "
            "order, never asks for personal data and never confirms a purchase: the customer "
            "enters their details and confirms in the interface. "
            "Returns: ready flag, the cart, the lines whose quantity exceeds the current stock "
            "and the next step to follow; an error when the cart is empty.",
            StartCheckoutArgs,
            checkout,
        ),
    ]
