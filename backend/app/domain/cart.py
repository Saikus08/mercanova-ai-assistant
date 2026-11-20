"""Cart entities and rules. Pure Python: no framework or persistence imports."""

from dataclasses import dataclass
from decimal import Decimal

MAX_QUANTITY_PER_LINE = 1000
CURRENCY = "USD"


class InvalidQuantity(Exception):
    """The quantity is not an integer between 1 and MAX_QUANTITY_PER_LINE."""


class InsufficientStock(Exception):
    def __init__(self, product_id: str, requested: int, available: int, in_cart: int = 0) -> None:
        super().__init__(f"Requested {requested} of {product_id}, only {available} available")
        self.product_id = product_id
        self.requested = requested
        self.available = available
        self.in_cart = in_cart  # units of the product the cart held before this request


class ProductInactive(Exception):
    """The product exists but cannot be sold (inactive, or without a price)."""

    def __init__(self, product_id: str) -> None:
        super().__init__(f"Product is not for sale: {product_id}")
        self.product_id = product_id


class ItemNotInCart(Exception):
    def __init__(self, product_id: str) -> None:
        super().__init__(f"Product not in cart: {product_id}")
        self.product_id = product_id


def validate_quantity(quantity: object) -> None:
    # bool is an int subclass, but True is not a quantity.
    if (
        not isinstance(quantity, int)
        or isinstance(quantity, bool)
        or not 1 <= quantity <= MAX_QUANTITY_PER_LINE
    ):
        raise InvalidQuantity(f"Quantity must be an integer from 1 to {MAX_QUANTITY_PER_LINE}")


def ensure_can_add(
    requested_total: int, available: int, product_id: str, added: int | None = None
) -> None:
    """Raise InsufficientStock when the quantity the line would hold exceeds the stock.

    ``added`` is the part of ``requested_total`` this request adds, so the error can say how many
    units the cart already held. Without it the error claims none, because it cannot know.
    """
    if requested_total > available:
        in_cart = 0 if added is None else requested_total - added
        raise InsufficientStock(product_id, requested_total, available, in_cart)


@dataclass(frozen=True)
class ProductStockInfo:
    """What the cart needs to know about a product, read from the database on every request."""

    product_id: str
    name: str
    active: bool
    has_price: bool
    available_qty: int


@dataclass(frozen=True)
class CartLine:
    product_id: str
    name: str
    image_url: str | None
    unit_price: Decimal
    quantity: int
    available_qty: int

    @property
    def line_total(self) -> Decimal:
        return self.unit_price * self.quantity


@dataclass(frozen=True)
class Cart:
    items: list[CartLine]
    currency: str = CURRENCY

    @property
    def item_count(self) -> int:
        return sum(line.quantity for line in self.items)

    @property
    def total(self) -> Decimal:
        return sum((line.line_total for line in self.items), Decimal("0"))
