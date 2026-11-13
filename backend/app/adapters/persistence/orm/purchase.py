"""Purchase tables (not in the dataset): cart, orders and per-warehouse stock allocations."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.adapters.persistence.base import Base, sql_in
from app.adapters.persistence.orm.stock import MONEY
from app.domain.order import DeliveryMethod, OrderStatus


class Cart(Base):
    __tablename__ = "carts"

    cart_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    session_id: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CartItem(Base):
    __tablename__ = "cart_items"
    __table_args__ = (CheckConstraint("quantity > 0", name="quantity_positive"),)

    cart_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("carts.cart_id", ondelete="CASCADE"), primary_key=True
    )
    product_id: Mapped[str] = mapped_column(
        ForeignKey("products.product_id"), primary_key=True, index=True
    )
    quantity: Mapped[int] = mapped_column(Integer)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint(sql_in("status", [s.value for s in OrderStatus]), name="status_valid"),
        CheckConstraint(
            sql_in("delivery_method", [m.value for m in DeliveryMethod]),
            name="delivery_method_valid",
        ),
        CheckConstraint(
            f"delivery_method <> '{DeliveryMethod.PICKUP.value}' OR warehouse_id IS NOT NULL",
            name="pickup_requires_warehouse",
        ),
        CheckConstraint("total >= 0", name="total_non_negative"),
    )

    # Human-readable id, e.g. ORD-20261112-0001.
    order_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(
        String(32), server_default=OrderStatus.PENDING_CONFIRMATION.value
    )
    customer_name: Mapped[str] = mapped_column(Text)
    customer_email: Mapped[str] = mapped_column(Text)
    customer_address: Mapped[str] = mapped_column(Text)
    delivery_method: Mapped[str] = mapped_column(String(16))
    warehouse_id: Mapped[str | None] = mapped_column(ForeignKey("warehouses.warehouse_id"))
    total: Mapped[Decimal] = mapped_column(MONEY)
    currency: Mapped[str] = mapped_column(String(3))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OrderItem(Base):
    """Order line. unit_price is copied at order creation so history shows what was paid."""

    __tablename__ = "order_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("unit_price >= 0", name="unit_price_non_negative"),
        CheckConstraint("line_total >= 0", name="line_total_non_negative"),
    )

    order_id: Mapped[str] = mapped_column(
        ForeignKey("orders.order_id", ondelete="CASCADE"), primary_key=True
    )
    product_id: Mapped[str] = mapped_column(
        ForeignKey("products.product_id"), primary_key=True, index=True
    )
    product_name: Mapped[str] = mapped_column(Text)
    unit_price: Mapped[Decimal] = mapped_column(MONEY)
    quantity: Mapped[int] = mapped_column(Integer)
    line_total: Mapped[Decimal] = mapped_column(MONEY)


class OrderAllocation(Base):
    """Which warehouse each confirmed unit of an order line was taken from."""

    __tablename__ = "order_allocations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["order_id", "product_id"],
            ["order_items.order_id", "order_items.product_id"],
            ondelete="CASCADE",
        ),
        CheckConstraint("quantity > 0", name="quantity_positive"),
    )

    order_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    product_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    warehouse_id: Mapped[str] = mapped_column(
        ForeignKey("warehouses.warehouse_id"), primary_key=True
    )
    quantity: Mapped[int] = mapped_column(Integer)
