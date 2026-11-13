"""Price and stock tables: dynamic data, always read from the database in the current turn."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.adapters.persistence.base import Base

MONEY = Numeric(10, 2)


class Price(Base):
    __tablename__ = "prices"
    __table_args__ = (
        CheckConstraint("list_price >= 0", name="list_price_non_negative"),
        CheckConstraint("current_price >= 0", name="current_price_non_negative"),
        CheckConstraint(
            "discount_percent >= 0 AND discount_percent <= 100", name="discount_percent_range"
        ),
    )

    product_id: Mapped[str] = mapped_column(
        ForeignKey("products.product_id", ondelete="CASCADE"), primary_key=True
    )
    currency: Mapped[str] = mapped_column(String(3))
    list_price: Mapped[Decimal] = mapped_column(MONEY)
    current_price: Mapped[Decimal] = mapped_column(MONEY)
    discount_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), server_default="0")
    tax_included: Mapped[bool] = mapped_column(Boolean, server_default="true")
    price_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Warehouse(Base):
    __tablename__ = "warehouses"

    warehouse_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    warehouse_name: Mapped[str] = mapped_column(Text)
    city: Mapped[str | None] = mapped_column(Text)
    department: Mapped[str | None] = mapped_column(Text)
    country: Mapped[str | None] = mapped_column(Text)
    pickup_enabled: Mapped[bool] = mapped_column(Boolean, server_default="true")
    shipping_enabled: Mapped[bool] = mapped_column(Boolean, server_default="true")


class Inventory(Base):
    __tablename__ = "inventory"
    __table_args__ = (
        CheckConstraint("on_hand_qty >= 0", name="on_hand_qty_non_negative"),
        CheckConstraint("reserved_qty >= 0", name="reserved_qty_non_negative"),
        CheckConstraint("available_qty >= 0", name="available_qty_non_negative"),
    )

    product_id: Mapped[str] = mapped_column(
        ForeignKey("products.product_id", ondelete="CASCADE"), primary_key=True
    )
    warehouse_id: Mapped[str] = mapped_column(
        ForeignKey("warehouses.warehouse_id"), primary_key=True, index=True
    )
    on_hand_qty: Mapped[int] = mapped_column(Integer)
    reserved_qty: Mapped[int] = mapped_column(Integer, server_default="0")
    available_qty: Mapped[int] = mapped_column(Integer)
    inventory_status: Mapped[str | None] = mapped_column(Text)
    inventory_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
