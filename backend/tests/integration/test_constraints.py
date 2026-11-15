"""The database itself rejects invalid operational data, whatever code writes it."""

from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.adapters.persistence.orm import (
    EMBEDDING_DIMENSIONS,
    Brand,
    Cart,
    CartItem,
    Inventory,
    Order,
    OrderAllocation,
    OrderItem,
    Product,
    ProductEmbedding,
    Warehouse,
)

pytestmark = pytest.mark.integration

PRODUCT_ID = "MN-MON-0001"
WAREHOUSE_ID = "WH-MVD-CEN"


@pytest.fixture
def catalog(db_session: Session) -> Session:
    """Minimal parent rows: one brand, one product, one warehouse."""
    db_session.add(Brand(brand_id="BR020", brand_name="Flux"))
    db_session.add(Warehouse(warehouse_id=WAREHOUSE_ID, warehouse_name="MercaNova Centro"))
    db_session.flush()
    db_session.add(
        Product(
            product_id=PRODUCT_ID,
            sku="MON-10000",
            name="Flux Vision 24 QHD IPS",
            brand_id="BR020",
            category_name="Monitors",
            subcategory_name="Gaming",
        )
    )
    db_session.flush()
    return db_session


def _order(**overrides: object) -> Order:
    values: dict[str, object] = {
        "order_id": "ORD-20261112-0001",
        "session_id": "session-1",
        "customer_name": "Ana Pérez",
        "customer_email": "ana@example.com",
        "customer_address": "Av. 18 de Julio 1234, Montevideo",
        "delivery_method": "pickup",
        "warehouse_id": WAREHOUSE_ID,
        "total": Decimal("937.24"),
        "currency": "USD",
    }
    values.update(overrides)
    return Order(**values)


def test_inventory_rejects_row_when_available_qty_is_negative(catalog: Session) -> None:
    catalog.add(
        Inventory(
            product_id=PRODUCT_ID,
            warehouse_id=WAREHOUSE_ID,
            on_hand_qty=0,
            reserved_qty=0,
            available_qty=-1,
        )
    )

    with pytest.raises(IntegrityError, match="ck_inventory_available_qty_non_negative"):
        catalog.flush()


def test_cart_item_rejects_row_when_quantity_is_zero(catalog: Session) -> None:
    cart = Cart(session_id="session-1")
    catalog.add(cart)
    catalog.flush()
    catalog.add(CartItem(cart_id=cart.cart_id, product_id=PRODUCT_ID, quantity=0))

    with pytest.raises(IntegrityError, match="ck_cart_items_quantity_positive"):
        catalog.flush()


def test_order_rejects_row_when_status_is_unknown(catalog: Session) -> None:
    catalog.add(_order(status="shipped"))

    with pytest.raises(IntegrityError, match="ck_orders_status_valid"):
        catalog.flush()


def test_order_rejects_row_when_pickup_has_no_warehouse(catalog: Session) -> None:
    catalog.add(_order(delivery_method="pickup", warehouse_id=None))

    with pytest.raises(IntegrityError, match="ck_orders_pickup_requires_warehouse"):
        catalog.flush()


def test_order_defaults_to_pending_confirmation_when_status_is_omitted(catalog: Session) -> None:
    catalog.add(_order())
    catalog.flush()

    status = catalog.scalar(select(Order.status).where(Order.order_id == "ORD-20261112-0001"))
    assert status == "pending_confirmation"


def test_order_allocation_rejects_row_when_order_line_does_not_exist(catalog: Session) -> None:
    catalog.add(_order())
    catalog.flush()
    catalog.add(
        OrderAllocation(
            order_id="ORD-20261112-0001",
            product_id=PRODUCT_ID,
            warehouse_id=WAREHOUSE_ID,
            quantity=1,
        )
    )

    constraint = "fk_order_allocations_order_id_product_id_order_items"
    with pytest.raises(IntegrityError, match=constraint):
        catalog.flush()


def test_order_allocation_is_accepted_when_it_references_an_order_line(catalog: Session) -> None:
    catalog.add(_order(status="confirmed"))
    catalog.flush()
    catalog.add(
        OrderItem(
            order_id="ORD-20261112-0001",
            product_id=PRODUCT_ID,
            product_name="Flux Vision 24 QHD IPS",
            unit_price=Decimal("468.62"),
            quantity=2,
            line_total=Decimal("937.24"),
        )
    )
    catalog.flush()
    catalog.add(
        OrderAllocation(
            order_id="ORD-20261112-0001",
            product_id=PRODUCT_ID,
            warehouse_id=WAREHOUSE_ID,
            quantity=2,
        )
    )
    catalog.flush()

    stored = catalog.get(OrderItem, ("ORD-20261112-0001", PRODUCT_ID))
    assert stored is not None
    assert stored.unit_price == Decimal("468.62")


def test_product_embedding_stores_vector_when_it_has_768_dimensions(catalog: Session) -> None:
    vector = [0.0] * EMBEDDING_DIMENSIONS
    vector[0] = 1.0
    catalog.add(
        ProductEmbedding(
            product_id=PRODUCT_ID,
            content="24-inch QHD IPS monitor",
            embedding=vector,
            model="nomic-embed-text",
        )
    )
    catalog.flush()
    catalog.expire_all()

    stored = catalog.get(ProductEmbedding, PRODUCT_ID)
    assert stored is not None
    assert len(stored.embedding) == EMBEDDING_DIMENSIONS
    assert stored.embedding[0] == pytest.approx(1.0)
