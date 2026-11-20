"""Cart use cases. Price and stock are read through the repository on every call."""

from app.application.ports import CartRepository
from app.domain.cart import (
    Cart,
    ItemNotInCart,
    ProductInactive,
    ProductStockInfo,
    ensure_can_add,
    validate_quantity,
)
from app.domain.catalog import ProductNotFound


def view_cart(repository: CartRepository, session_id: str) -> Cart:
    return Cart(items=repository.get_lines(session_id))


def _sellable_product(repository: CartRepository, product_id: str) -> ProductStockInfo:
    info = repository.product_stock_info(product_id)
    if info is None:
        raise ProductNotFound(product_id)
    # A product without a price row cannot be bought, so it is reported like an inactive one.
    if not info.active or not info.has_price:
        raise ProductInactive(product_id)
    return info


def add_item(repository: CartRepository, session_id: str, product_id: str, quantity: int) -> Cart:
    validate_quantity(quantity)
    info = _sellable_product(repository, product_id)
    repository.add_quantity(
        session_id,
        product_id,
        quantity,
        lambda requested_total: ensure_can_add(
            requested_total, info.available_qty, product_id, added=quantity
        ),
    )
    return view_cart(repository, session_id)


def set_quantity(
    repository: CartRepository, session_id: str, product_id: str, quantity: int
) -> Cart:
    validate_quantity(quantity)
    info = _sellable_product(repository, product_id)
    in_cart = repository.set_quantity(
        session_id,
        product_id,
        quantity,
        lambda requested_total: ensure_can_add(requested_total, info.available_qty, product_id),
    )
    if not in_cart:
        raise ItemNotInCart(product_id)
    return view_cart(repository, session_id)


def remove_item(repository: CartRepository, session_id: str, product_id: str) -> Cart:
    repository.remove_item(session_id, product_id)
    return view_cart(repository, session_id)


def clear_cart(repository: CartRepository, session_id: str) -> Cart:
    repository.clear(session_id)
    return view_cart(repository, session_id)
