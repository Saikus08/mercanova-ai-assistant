"""Purchase rules: checkout validation, stock checks and order confirmation. Pure Python."""

import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from app.domain.cart import InsufficientStock, ProductInactive
from app.domain.order import DeliveryMethod, OrderStatus

MAX_NAME_LENGTH = 120
MAX_EMAIL_LENGTH = 254
MAX_ADDRESS_LENGTH = 300
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class CartEmpty(Exception):
    """Checkout was requested with nothing in the cart."""


class OrderNotFound(Exception):
    """The order does not exist or belongs to another session."""


class OrderNotPending(Exception):
    """Only a pending order can be confirmed or cancelled."""


class PriceChanged(Exception):
    def __init__(self, product_id: str, old_price: Decimal, new_price: Decimal) -> None:
        super().__init__(f"Price of {product_id} changed from {old_price} to {new_price}")
        self.product_id = product_id
        self.old_price = old_price
        self.new_price = new_price


class InvalidCheckout(Exception):
    """Customer or delivery data is not valid. ``errors`` holds (field, message) pairs.

    Messages never include the submitted values: they are personal data.
    """

    def __init__(self, errors: list[tuple[str, str]]) -> None:
        super().__init__("Invalid checkout data")
        self.errors = errors


@dataclass(frozen=True)
class Customer:
    # repr is hidden so the data cannot leak through logs or tracebacks.
    name: str = field(repr=False)
    email: str = field(repr=False)
    address: str = field(repr=False)


@dataclass(frozen=True)
class Delivery:
    method: DeliveryMethod
    warehouse_id: str | None = None


@dataclass(frozen=True)
class DeliveryOption:
    """What a warehouse allows; used to validate the chosen delivery."""

    warehouse_id: str
    pickup_enabled: bool
    shipping_enabled: bool


@dataclass(frozen=True)
class StockRow:
    product_id: str
    warehouse_id: str
    available_qty: int
    shipping_enabled: bool


@dataclass(frozen=True)
class OrderLine:
    product_id: str
    name: str
    unit_price: Decimal
    quantity: int
    line_total: Decimal


@dataclass(frozen=True)
class Order:
    order_id: str
    status: OrderStatus
    created_at: datetime
    confirmed_at: datetime | None
    customer: Customer
    delivery: Delivery
    items: list[OrderLine]
    total: Decimal
    currency: str


@dataclass(frozen=True)
class Allocation:
    product_id: str
    warehouse_id: str
    quantity: int


@dataclass(frozen=True)
class ConfirmationPlan:
    allocations: list[Allocation]


def validate_checkout(
    customer: Customer, delivery: Delivery, options: list[DeliveryOption]
) -> tuple[Customer, Delivery]:
    """Return the trimmed customer and the delivery to store, or raise InvalidCheckout."""
    errors: list[tuple[str, str]] = []
    values = {}
    for name, limit in (
        ("name", MAX_NAME_LENGTH),
        ("email", MAX_EMAIL_LENGTH),
        ("address", MAX_ADDRESS_LENGTH),
    ):
        value = getattr(customer, name).strip()
        values[name] = value
        if not value:
            errors.append((f"customer.{name}", "Must not be blank."))
        elif len(value) > limit:
            errors.append((f"customer.{name}", f"Must be at most {limit} characters."))
        elif name == "email" and not _EMAIL.match(value):
            errors.append(("customer.email", "Must be a valid email address."))

    warehouse_id = (delivery.warehouse_id or "").strip() or None
    if delivery.method is DeliveryMethod.PICKUP:
        chosen = next((o for o in options if o.warehouse_id == warehouse_id), None)
        if warehouse_id is None:
            errors.append(("delivery.warehouse_id", "Required for pickup."))
        elif chosen is None or not chosen.pickup_enabled:
            errors.append(("delivery.warehouse_id", "Must be a warehouse that allows pickup."))
    else:
        warehouse_id = None  # shipping is served from any warehouse that ships
        if not any(o.shipping_enabled for o in options):
            errors.append(("delivery.method", "Shipping is not available."))

    if errors:
        raise InvalidCheckout(errors)
    return Customer(**values), Delivery(delivery.method, warehouse_id)


def _sources(delivery: Delivery, rows: list[StockRow], product_id: str) -> list[StockRow]:
    """Rows the product may be taken from, in the order they are consumed."""
    rows = [r for r in rows if r.product_id == product_id and r.available_qty > 0]
    if delivery.method is DeliveryMethod.PICKUP:
        return [r for r in rows if r.warehouse_id == delivery.warehouse_id]
    shipping = [r for r in rows if r.shipping_enabled]
    return sorted(shipping, key=lambda r: (-r.available_qty, r.warehouse_id))


def check_stock(wanted: list[tuple[str, int]], delivery: Delivery, rows: list[StockRow]) -> None:
    """Raise InsufficientStock for the first line the delivery rule cannot cover."""
    for product_id, quantity in wanted:
        available = sum(r.available_qty for r in _sources(delivery, rows, product_id))
        if quantity > available:
            raise InsufficientStock(product_id, quantity, available)


def plan_confirmation(
    order: Order, current_prices: dict[str, Decimal], stock_rows: list[StockRow]
) -> ConfirmationPlan:
    """Decide whether the order can be confirmed now and from which warehouses it is served.

    Stock is checked first, then prices. ``current_prices`` only holds products that are
    still for sale.
    """
    check_stock([(i.product_id, i.quantity) for i in order.items], order.delivery, stock_rows)
    for item in order.items:
        current = current_prices.get(item.product_id)
        if current is None:
            raise ProductInactive(item.product_id)
        if current != item.unit_price:
            raise PriceChanged(item.product_id, item.unit_price, current)

    allocations = []
    for item in order.items:
        remaining = item.quantity
        for source in _sources(order.delivery, stock_rows, item.product_id):
            taken = min(source.available_qty, remaining)
            allocations.append(Allocation(item.product_id, source.warehouse_id, taken))
            remaining -= taken
            if remaining == 0:
                break
    return ConfirmationPlan(allocations)
