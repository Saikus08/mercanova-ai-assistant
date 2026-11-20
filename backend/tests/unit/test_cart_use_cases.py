"""Cart rules and use cases with a fake repository (no database)."""

from collections.abc import Callable
from decimal import Decimal

import pytest

from app.application.cart import add_item, clear_cart, remove_item, set_quantity, view_cart
from app.domain.cart import (
    MAX_QUANTITY_PER_LINE,
    CartLine,
    InsufficientStock,
    InvalidQuantity,
    ItemNotInCart,
    ProductInactive,
    ProductStockInfo,
    ensure_can_add,
    validate_quantity,
)
from app.domain.catalog import ProductNotFound

SESSION = "session-a"


class FakeCartRepository:
    def __init__(self) -> None:
        self.products: dict[str, ProductStockInfo] = {}
        self.prices: dict[str, Decimal] = {}
        self.carts: dict[str, dict[str, int]] = {}

    def sell(
        self, product_id: str, price: str, available: int, active: bool = True, has_price=True
    ) -> None:
        self.products[product_id] = ProductStockInfo(
            product_id, f"Product {product_id}", active, has_price, available
        )
        self.prices[product_id] = Decimal(price)

    def get_lines(self, session_id: str) -> list[CartLine]:
        lines = []
        for product_id, quantity in self.carts.get(session_id, {}).items():
            info = self.products[product_id]
            lines.append(
                CartLine(
                    product_id,
                    info.name,
                    None,
                    self.prices[product_id],
                    quantity,
                    info.available_qty,
                )
            )
        return lines

    def product_stock_info(self, product_id: str) -> ProductStockInfo | None:
        return self.products.get(product_id)

    def add_quantity(
        self, session_id: str, product_id: str, quantity: int, check: Callable[[int], None]
    ) -> None:
        cart = self.carts.setdefault(session_id, {})
        total = cart.get(product_id, 0) + quantity
        check(total)
        cart[product_id] = total

    def set_quantity(
        self, session_id: str, product_id: str, quantity: int, check: Callable[[int], None]
    ) -> bool:
        cart = self.carts.setdefault(session_id, {})
        if product_id not in cart:
            return False
        check(quantity)
        cart[product_id] = quantity
        return True

    def remove_item(self, session_id: str, product_id: str) -> None:
        self.carts.get(session_id, {}).pop(product_id, None)

    def clear(self, session_id: str) -> None:
        self.carts.pop(session_id, None)


@pytest.fixture
def repo() -> FakeCartRepository:
    repository = FakeCartRepository()
    repository.sell("P1", "100.00", 7)
    repository.sell("P2", "19.99", 20)
    repository.sell("OLD", "10.00", 5, active=False)
    repository.sell("NOPRICE", "0", 5, has_price=False)
    return repository


def quantities(repo: FakeCartRepository, session_id: str = SESSION) -> dict[str, int]:
    return dict(repo.carts.get(session_id, {}))


# --- domain rules ---


@pytest.mark.parametrize("value", [1, 5, MAX_QUANTITY_PER_LINE])
def test_validate_quantity_accepts_range(value):
    validate_quantity(value)


@pytest.mark.parametrize("value", [0, -1, MAX_QUANTITY_PER_LINE + 1, True, 1.5, "2"])
def test_validate_quantity_rejects_out_of_range_or_non_int(value):
    with pytest.raises(InvalidQuantity):
        validate_quantity(value)


def test_ensure_can_add_allows_up_to_available():
    ensure_can_add(7, 7, "P1")


def test_ensure_can_add_raises_with_details():
    with pytest.raises(InsufficientStock) as error:
        ensure_can_add(8, 7, "P1")
    assert (error.value.product_id, error.value.requested, error.value.available) == ("P1", 8, 7)


def test_ensure_can_add_reports_what_the_cart_already_held():
    with pytest.raises(InsufficientStock) as error:
        ensure_can_add(8, 7, "P1", added=3)
    assert error.value.in_cart == 5


# --- use cases ---


def test_view_empty_cart(repo):
    cart = view_cart(repo, SESSION)
    assert cart.items == []
    assert cart.item_count == 0
    assert cart.total == Decimal("0")
    assert cart.currency == "USD"


def test_add_new_item(repo):
    cart = add_item(repo, SESSION, "P1", 2)
    assert quantities(repo) == {"P1": 2}
    assert cart.items[0].line_total == Decimal("200.00")


def test_add_accumulates_quantity(repo):
    add_item(repo, SESSION, "P1", 2)
    cart = add_item(repo, SESSION, "P1", 3)
    assert quantities(repo) == {"P1": 5}
    assert cart.item_count == 5


def test_add_beyond_available_with_existing_quantity_fails_and_keeps_cart(repo):
    add_item(repo, SESSION, "P1", 5)
    with pytest.raises(InsufficientStock) as error:
        add_item(repo, SESSION, "P1", 3)
    assert (error.value.requested, error.value.available) == (8, 7)
    assert quantities(repo) == {"P1": 5}


def test_add_exactly_available_is_allowed(repo):
    add_item(repo, SESSION, "P1", 7)
    assert quantities(repo) == {"P1": 7}


def test_add_more_than_available_to_empty_cart_creates_nothing(repo):
    with pytest.raises(InsufficientStock):
        add_item(repo, SESSION, "P1", 50)
    assert quantities(repo) == {}


def test_add_inactive_product_fails(repo):
    with pytest.raises(ProductInactive) as error:
        add_item(repo, SESSION, "OLD", 1)
    assert error.value.product_id == "OLD"
    assert quantities(repo) == {}


def test_add_product_without_price_fails_as_inactive(repo):
    with pytest.raises(ProductInactive):
        add_item(repo, SESSION, "NOPRICE", 1)


def test_add_unknown_product_fails(repo):
    with pytest.raises(ProductNotFound):
        add_item(repo, SESSION, "NOPE", 1)


@pytest.mark.parametrize("quantity", [0, -3, MAX_QUANTITY_PER_LINE + 1])
def test_add_invalid_quantity_fails_before_touching_cart(repo, quantity):
    with pytest.raises(InvalidQuantity):
        add_item(repo, SESSION, "P1", quantity)
    assert quantities(repo) == {}


def test_set_quantity_replaces_value(repo):
    add_item(repo, SESSION, "P1", 5)
    cart = set_quantity(repo, SESSION, "P1", 2)
    assert quantities(repo) == {"P1": 2}
    assert cart.item_count == 2


def test_set_quantity_above_stock_fails_and_keeps_cart(repo):
    add_item(repo, SESSION, "P1", 2)
    with pytest.raises(InsufficientStock) as error:
        set_quantity(repo, SESSION, "P1", 8)
    assert error.value.available == 7
    assert quantities(repo) == {"P1": 2}


def test_set_quantity_of_item_not_in_cart_fails(repo):
    with pytest.raises(ItemNotInCart) as error:
        set_quantity(repo, SESSION, "P1", 1)
    assert error.value.product_id == "P1"


def test_set_quantity_of_unknown_product_fails(repo):
    with pytest.raises(ProductNotFound):
        set_quantity(repo, SESSION, "NOPE", 1)


@pytest.mark.parametrize("quantity", [0, -1, MAX_QUANTITY_PER_LINE + 1])
def test_set_quantity_invalid_quantity_fails(repo, quantity):
    add_item(repo, SESSION, "P1", 2)
    with pytest.raises(InvalidQuantity):
        set_quantity(repo, SESSION, "P1", quantity)
    assert quantities(repo) == {"P1": 2}


def test_remove_item(repo):
    add_item(repo, SESSION, "P1", 2)
    add_item(repo, SESSION, "P2", 1)
    cart = remove_item(repo, SESSION, "P1")
    assert [line.product_id for line in cart.items] == ["P2"]


def test_remove_item_is_idempotent(repo):
    add_item(repo, SESSION, "P2", 1)
    cart = remove_item(repo, SESSION, "P1")
    assert [line.product_id for line in cart.items] == ["P2"]
    assert remove_item(repo, "other-session", "P1").items == []


def test_clear_cart(repo):
    add_item(repo, SESSION, "P1", 2)
    assert clear_cart(repo, SESSION).items == []
    assert clear_cart(repo, SESSION).items == []


def test_totals_and_item_count(repo):
    add_item(repo, SESSION, "P1", 2)
    cart = add_item(repo, SESSION, "P2", 3)
    assert cart.item_count == 5
    assert cart.total == Decimal("259.97")
    assert [line.line_total for line in cart.items] == [Decimal("200.00"), Decimal("59.97")]


def test_carts_are_separated_by_session(repo):
    add_item(repo, "session-a", "P1", 2)
    assert view_cart(repo, "session-b").items == []


def test_add_item_over_the_stock_reports_how_many_were_already_in_the_cart(repo):
    add_item(repo, SESSION, "P1", 5)

    with pytest.raises(InsufficientStock) as error:
        add_item(repo, SESSION, "P1", 3)

    assert error.value.in_cart == 5
