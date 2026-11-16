"""SQLAlchemy implementation of the OrderRepository port.

Confirmation runs in one transaction. Locks are always taken in the same order (the order row,
then the inventory rows sorted by product and warehouse) so concurrent confirmations cannot
deadlock, and a second buyer of the last unit waits and then sees the updated stock.
"""

from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import Integer, cast, delete, func, select, update
from sqlalchemy.orm import Session

from app.adapters.persistence.orm.catalog import Product
from app.adapters.persistence.orm.purchase import Cart, CartItem, OrderAllocation, OrderItem
from app.adapters.persistence.orm.purchase import Order as OrderRow
from app.adapters.persistence.orm.stock import Inventory, Price, Warehouse
from app.domain.order import DeliveryMethod, OrderStatus
from app.domain.purchase import (
    Allocation,
    ConfirmationPlan,
    Customer,
    Delivery,
    DeliveryOption,
    Order,
    OrderLine,
    OrderNotFound,
    OrderNotPending,
    StockRow,
)

CURRENCY = "USD"


class SqlAlchemyOrderRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def delivery_options(self) -> list[DeliveryOption]:
        rows = self._session.execute(
            select(Warehouse.warehouse_id, Warehouse.pickup_enabled, Warehouse.shipping_enabled)
        ).all()
        return [DeliveryOption(r[0], bool(r[1]), bool(r[2])) for r in rows]

    def _stock_query(self, product_ids: list[str]):
        return (
            select(
                Inventory.product_id,
                Inventory.warehouse_id,
                Inventory.available_qty,
                Warehouse.shipping_enabled,
            )
            .join(Warehouse, Warehouse.warehouse_id == Inventory.warehouse_id)
            .where(Inventory.product_id.in_(product_ids))
            .order_by(Inventory.product_id, Inventory.warehouse_id)
        )

    @staticmethod
    def _stock_rows(rows) -> list[StockRow]:
        return [StockRow(r[0], r[1], int(r[2]), bool(r[3])) for r in rows]

    def stock_rows(self, product_ids: list[str]) -> list[StockRow]:
        return self._stock_rows(self._session.execute(self._stock_query(product_ids)).all())

    def _next_order_number(self, today: str) -> str:
        """Next ``ORD-YYYYMMDD-NNNN``. The advisory lock serializes writers of the same day."""
        self._session.execute(select(func.pg_advisory_xact_lock(int(today))))
        prefix = f"ORD-{today}-"
        last = self._session.scalar(
            select(func.max(cast(func.substr(OrderRow.order_id, len(prefix) + 1), Integer))).where(
                OrderRow.order_id.like(f"{prefix}%")
            )
        )
        return f"{prefix}{(last or 0) + 1:04d}"

    def create(
        self,
        session_id: str,
        customer: Customer,
        delivery: Delivery,
        items: list[OrderLine],
        total: Decimal,
    ) -> Order:
        try:
            order_id = self._next_order_number(datetime.now(UTC).strftime("%Y%m%d"))
            row = OrderRow(
                order_id=order_id,
                session_id=session_id,
                status=OrderStatus.PENDING_CONFIRMATION.value,
                customer_name=customer.name,
                customer_email=customer.email,
                customer_address=customer.address,
                delivery_method=delivery.method.value,
                warehouse_id=delivery.warehouse_id,
                total=total,
                currency=CURRENCY,
            )
            self._session.add(row)
            self._session.flush()  # the order must exist before its lines
            self._session.add_all(
                OrderItem(
                    order_id=order_id,
                    product_id=item.product_id,
                    product_name=item.name,
                    unit_price=item.unit_price,
                    quantity=item.quantity,
                    line_total=item.line_total,
                )
                for item in items
            )
            self._session.flush()
            self._session.refresh(row)
            created = self._to_order(row, items)
            self._session.commit()
            return created
        except BaseException:
            self._session.rollback()
            raise

    def confirm(
        self,
        order_id: str,
        session_id: str,
        decide: Callable[[Order, dict[str, Decimal], list[StockRow]], ConfirmationPlan],
    ) -> Order:
        try:
            row = self._lock_pending(order_id, session_id)
            order = self._to_order(row, self._items(order_id))
            product_ids = [item.product_id for item in order.items]
            locked = self._session.execute(
                self._stock_query(product_ids).with_for_update(of=Inventory)
            ).all()
            plan = decide(order, self._current_prices(product_ids), self._stock_rows(locked))
            for allocation in plan.allocations:
                self._allocate(order_id, allocation)
            row.status = OrderStatus.CONFIRMED.value
            row.confirmed_at = func.now()
            self._session.execute(
                delete(CartItem).where(
                    CartItem.cart_id.in_(select(Cart.cart_id).where(Cart.session_id == session_id))
                )
            )
            self._session.flush()
            self._session.refresh(row)
            confirmed = self._to_order(row, order.items)
            self._session.commit()
            return confirmed
        except BaseException:
            self._session.rollback()
            raise

    def cancel(self, order_id: str, session_id: str) -> Order:
        try:
            row = self._lock_pending(order_id, session_id)
            row.status = OrderStatus.CANCELLED.value
            row.cancelled_at = func.now()
            self._session.flush()
            self._session.refresh(row)
            cancelled = self._to_order(row, self._items(order_id))
            self._session.commit()
            return cancelled
        except BaseException:
            self._session.rollback()
            raise

    def _lock_pending(self, order_id: str, session_id: str) -> OrderRow:
        """Lock the order row; it must belong to the session and still be pending."""
        row = self._session.execute(
            select(OrderRow)
            .where(OrderRow.order_id == order_id, OrderRow.session_id == session_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        ).scalar_one_or_none()
        if row is None:
            raise OrderNotFound
        if row.status != OrderStatus.PENDING_CONFIRMATION.value:
            raise OrderNotPending
        return row

    def _items(self, order_id: str) -> list[OrderLine]:
        rows = self._session.execute(
            select(
                OrderItem.product_id,
                OrderItem.product_name,
                OrderItem.unit_price,
                OrderItem.quantity,
                OrderItem.line_total,
            )
            .where(OrderItem.order_id == order_id)
            .order_by(OrderItem.product_id)
        ).all()
        return [OrderLine(r[0], r[1], r[2], r[3], r[4]) for r in rows]

    def _current_prices(self, product_ids: list[str]) -> dict[str, Decimal]:
        """Current price of the products that are still for sale."""
        rows = self._session.execute(
            select(Price.product_id, Price.current_price)
            .join(Product, Product.product_id == Price.product_id)
            .where(Price.product_id.in_(product_ids), Product.active.is_(True))
        ).all()
        return {r[0]: r[1] for r in rows}

    def _allocate(self, order_id: str, allocation: Allocation) -> None:
        # on_hand and available drop together, so available = on_hand - reserved still holds.
        self._session.execute(
            update(Inventory)
            .where(
                Inventory.product_id == allocation.product_id,
                Inventory.warehouse_id == allocation.warehouse_id,
            )
            .values(
                on_hand_qty=Inventory.on_hand_qty - allocation.quantity,
                available_qty=Inventory.available_qty - allocation.quantity,
                inventory_updated_at=func.now(),
            )
        )
        self._session.add(
            OrderAllocation(
                order_id=order_id,
                product_id=allocation.product_id,
                warehouse_id=allocation.warehouse_id,
                quantity=allocation.quantity,
            )
        )

    @staticmethod
    def _to_order(row: OrderRow, items: list[OrderLine]) -> Order:
        return Order(
            order_id=row.order_id,
            status=OrderStatus(row.status),
            created_at=row.created_at,
            confirmed_at=row.confirmed_at,
            customer=Customer(row.customer_name, row.customer_email, row.customer_address),
            delivery=Delivery(DeliveryMethod(row.delivery_method), row.warehouse_id),
            items=items,
            total=row.total,
            currency=row.currency,
        )
