"""Two-step purchase use cases.

Confirming and cancelling exist only as user-triggered endpoints. They are never exposed as
tools of the shopping assistant.
"""

from decimal import Decimal

from app.application.ports import CartRepository, OrderRepository
from app.domain.cart import ProductInactive
from app.domain.purchase import (
    CartEmpty,
    Customer,
    Delivery,
    Order,
    OrderLine,
    check_stock,
    plan_confirmation,
    validate_checkout,
)

CENTS = Decimal("0.01")


def checkout(
    cart_repository: CartRepository,
    order_repository: OrderRepository,
    session_id: str,
    customer: Customer,
    delivery: Delivery,
) -> Order:
    """Step 1: create a pending order from the cart. Stock and cart are left untouched."""
    customer, delivery = validate_checkout(customer, delivery, order_repository.delivery_options())
    lines = cart_repository.get_lines(session_id)
    if not lines:
        raise CartEmpty
    for line in lines:
        info = cart_repository.product_stock_info(line.product_id)
        if info is None or not info.active or not info.has_price:
            raise ProductInactive(line.product_id)
    rows = order_repository.stock_rows([line.product_id for line in lines])
    check_stock([(line.product_id, line.quantity) for line in lines], delivery, rows)

    items = [
        OrderLine(
            line.product_id,
            line.name,
            line.unit_price,
            line.quantity,
            (line.unit_price * line.quantity).quantize(CENTS),
        )
        for line in lines
    ]
    total = sum((item.line_total for item in items), Decimal("0"))
    return order_repository.create(session_id, customer, delivery, items, total)


def confirm_order(order_repository: OrderRepository, session_id: str, order_id: str) -> Order:
    """Step 2: the repository runs the transaction, the domain decides what is allowed."""
    return order_repository.confirm(order_id, session_id, plan_confirmation)


def cancel_order(order_repository: OrderRepository, session_id: str, order_id: str) -> Order:
    return order_repository.cancel(order_id, session_id)


def list_orders(order_repository: OrderRepository, session_id: str) -> list[Order]:
    """Order history (RF-16). Lines keep the name and price copied when the order was created."""
    return order_repository.list_for_session(session_id)


def get_order(order_repository: OrderRepository, session_id: str, order_id: str) -> Order:
    return order_repository.get(order_id, session_id)
