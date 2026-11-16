"""SQLAlchemy implementation of the CartRepository port.

The cart tables hold only product and quantity. Name, image, price and stock are joined in
every read, so each call reflects the current database state.
"""

import uuid
from collections.abc import Callable

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.adapters.persistence.orm.catalog import Product
from app.adapters.persistence.orm.purchase import Cart, CartItem
from app.adapters.persistence.orm.stock import Inventory, Price
from app.domain.cart import CartLine, ProductStockInfo

_stock = (
    select(Inventory.product_id, func.sum(Inventory.available_qty).label("qty"))
    .group_by(Inventory.product_id)
    .subquery("stock")
)


class SqlAlchemyCartRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_lines(self, session_id: str) -> list[CartLine]:
        # Inner join on prices: a line whose price row disappeared cannot be shown or bought.
        rows = self._session.execute(
            select(
                Product.product_id,
                Product.name,
                Product.image_url,
                Price.current_price,
                CartItem.quantity,
                func.coalesce(_stock.c.qty, 0),
            )
            .select_from(CartItem)
            .join(Cart, Cart.cart_id == CartItem.cart_id)
            .join(Product, Product.product_id == CartItem.product_id)
            .join(Price, Price.product_id == Product.product_id)
            .outerjoin(_stock, _stock.c.product_id == Product.product_id)
            .where(Cart.session_id == session_id)
            .order_by(CartItem.added_at, CartItem.product_id)
        ).all()
        return [CartLine(r[0], r[1], r[2], r[3], r[4], int(r[5])) for r in rows]

    def product_stock_info(self, product_id: str) -> ProductStockInfo | None:
        row = self._session.execute(
            select(
                Product.product_id,
                Product.name,
                Product.active,
                Price.product_id.is_not(None),
                func.coalesce(_stock.c.qty, 0),
            )
            .outerjoin(Price, Price.product_id == Product.product_id)
            .outerjoin(_stock, _stock.c.product_id == Product.product_id)
            .where(Product.product_id == product_id)
        ).first()
        if row is None:
            return None
        return ProductStockInfo(row[0], row[1], bool(row[2]), bool(row[3]), int(row[4]))

    def _lock_cart(self, session_id: str) -> uuid.UUID:
        """Create the cart row on first use and lock it so one session's writes serialize."""
        self._session.execute(
            insert(Cart)
            .values(cart_id=uuid.uuid4(), session_id=session_id)
            .on_conflict_do_nothing(index_elements=[Cart.session_id])
        )
        return self._session.execute(
            select(Cart.cart_id).where(Cart.session_id == session_id).with_for_update()
        ).scalar_one()

    def _current_quantity(self, cart_id: uuid.UUID, product_id: str) -> int | None:
        return self._session.scalar(
            select(CartItem.quantity).where(
                CartItem.cart_id == cart_id, CartItem.product_id == product_id
            )
        )

    def _write_line(self, cart_id: uuid.UUID, product_id: str, quantity: int) -> None:
        self._session.execute(
            insert(CartItem)
            .values(cart_id=cart_id, product_id=product_id, quantity=quantity)
            .on_conflict_do_update(
                index_elements=[CartItem.cart_id, CartItem.product_id],
                set_={"quantity": quantity},
            )
        )
        self._session.execute(
            update(Cart).where(Cart.cart_id == cart_id).values(updated_at=func.now())
        )

    def add_quantity(
        self, session_id: str, product_id: str, quantity: int, check: Callable[[int], None]
    ) -> None:
        try:
            cart_id = self._lock_cart(session_id)
            total = (self._current_quantity(cart_id, product_id) or 0) + quantity
            check(total)
            self._write_line(cart_id, product_id, total)
            self._session.commit()
        except BaseException:
            self._session.rollback()
            raise

    def set_quantity(
        self, session_id: str, product_id: str, quantity: int, check: Callable[[int], None]
    ) -> bool:
        try:
            cart_id = self._lock_cart(session_id)
            if self._current_quantity(cart_id, product_id) is None:
                self._session.commit()  # keeps the lazily created, empty cart row
                return False
            check(quantity)
            self._write_line(cart_id, product_id, quantity)
            self._session.commit()
            return True
        except BaseException:
            self._session.rollback()
            raise

    def remove_item(self, session_id: str, product_id: str) -> None:
        self._session.execute(
            delete(CartItem).where(
                CartItem.product_id == product_id,
                CartItem.cart_id.in_(select(Cart.cart_id).where(Cart.session_id == session_id)),
            )
        )
        self._session.commit()

    def clear(self, session_id: str) -> None:
        self._session.execute(
            delete(CartItem).where(
                CartItem.cart_id.in_(select(Cart.cart_id).where(Cart.session_id == session_id))
            )
        )
        self._session.commit()
