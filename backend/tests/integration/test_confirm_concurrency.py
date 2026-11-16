"""Concurrent confirmations against real committed data (no rollback fixture).

Each thread has its own session, so the row locks of the confirmation are really contended.
Everything the tests commit uses ids starting with CC- and is deleted on teardown.
"""

import threading
from collections.abc import Callable, Iterator
from decimal import Decimal

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from app.adapters.persistence.order_repository import SqlAlchemyOrderRepository
from app.adapters.persistence.orm.catalog import Brand, Category, Product
from app.adapters.persistence.orm.purchase import Order, OrderItem
from app.adapters.persistence.orm.stock import Inventory, Price, Warehouse
from app.application.checkout import confirm_order
from app.domain.cart import InsufficientStock
from app.domain.purchase import OrderNotPending

pytestmark = pytest.mark.integration

# FK order: children first.
CLEANUP = [
    "DELETE FROM order_allocations WHERE order_id LIKE 'CC-%'",
    "DELETE FROM order_items WHERE order_id LIKE 'CC-%'",
    "DELETE FROM orders WHERE order_id LIKE 'CC-%'",
    "DELETE FROM cart_items WHERE cart_id IN "
    "(SELECT cart_id FROM carts WHERE session_id LIKE 'cc-%')",
    "DELETE FROM carts WHERE session_id LIKE 'cc-%'",
    "DELETE FROM inventory WHERE product_id LIKE 'CC-%'",
    "DELETE FROM prices WHERE product_id LIKE 'CC-%'",
    "DELETE FROM products WHERE product_id LIKE 'CC-%'",
    "DELETE FROM brands WHERE brand_id LIKE 'CC-%'",
    "DELETE FROM categories WHERE subcategory_id LIKE 'CC-%'",
    "DELETE FROM warehouses WHERE warehouse_id LIKE 'CC-%'",
]


def clean(engine: Engine) -> None:
    with Session(engine) as session:
        for statement in CLEANUP:
            session.execute(text(statement))
        session.commit()


@pytest.fixture
def committed_data(migrated_engine: Engine) -> Iterator[Callable[[int, list[str]], None]]:
    """Factory: one product with ``units`` in one warehouse and one pending order per session."""
    clean(migrated_engine)

    def create(units: int, sessions: list[str]) -> None:
        with Session(migrated_engine) as session:
            session.add_all(
                [
                    Brand(brand_id="CC-B", brand_name="Concurrent"),
                    Category(
                        subcategory_id="CC-SC",
                        subcategory_name="CC sub",
                        category_id="CC-C",
                        category_name="CC category",
                    ),
                    Warehouse(warehouse_id="CC-W1", warehouse_name="Concurrent"),
                ]
            )
            session.flush()
            session.add(
                Product(
                    product_id="CC-P1",
                    sku="CC-SKU-1",
                    name="Last unit",
                    brand_id="CC-B",
                    subcategory_id="CC-SC",
                    category_name="CC category",
                    subcategory_name="CC sub",
                )
            )
            session.flush()
            session.add_all(
                [
                    Price(
                        product_id="CC-P1",
                        currency="USD",
                        list_price="10.00",
                        current_price="10.00",
                        discount_percent=0,
                    ),
                    Inventory(
                        product_id="CC-P1",
                        warehouse_id="CC-W1",
                        on_hand_qty=units,
                        available_qty=units,
                    ),
                ]
            )
            for index, session_id in enumerate(sessions):
                order_id = f"CC-ORDER-{index}"
                session.add(
                    Order(
                        order_id=order_id,
                        session_id=session_id,
                        status="pending_confirmation",
                        customer_name="Concurrent Buyer",
                        customer_email="buyer@example.com",
                        customer_address="Calle 1",
                        delivery_method="pickup",
                        warehouse_id="CC-W1",
                        total=Decimal("10.00"),
                        currency="USD",
                    )
                )
                session.flush()
                session.add(
                    OrderItem(
                        order_id=order_id,
                        product_id="CC-P1",
                        product_name="Last unit",
                        unit_price=Decimal("10.00"),
                        quantity=1,
                        line_total=Decimal("10.00"),
                    )
                )
            session.commit()

    try:
        yield create
    finally:
        clean(migrated_engine)


def run_together(engine: Engine, attempts: list[tuple[str, str]]) -> list[object]:
    """Confirm every (session_id, order_id) from its own thread, released at the same moment.

    Returns the order for each success or the raised exception, in the order of ``attempts``.
    """
    barrier = threading.Barrier(len(attempts))
    results: list[object] = [None] * len(attempts)

    def worker(index: int, session_id: str, order_id: str) -> None:
        with Session(engine) as session:
            repository = SqlAlchemyOrderRepository(session)
            barrier.wait(timeout=10)
            try:
                results[index] = confirm_order(repository, session_id, order_id)
            except Exception as error:
                results[index] = error

    threads = [
        threading.Thread(target=worker, args=(i, session_id, order_id))
        for i, (session_id, order_id) in enumerate(attempts)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
        assert not thread.is_alive(), "a confirmation is stuck (possible deadlock)"
    return results


def scalar(engine: Engine, statement: str) -> object:
    with Session(engine) as session:
        return session.execute(text(statement)).scalar_one()


def test_two_sessions_competing_for_the_last_unit(migrated_engine: Engine, committed_data):
    committed_data(1, ["cc-a", "cc-b"])

    results = run_together(migrated_engine, [("cc-a", "CC-ORDER-0"), ("cc-b", "CC-ORDER-1")])

    failures = [r for r in results if isinstance(r, InsufficientStock)]
    successes = [r for r in results if not isinstance(r, Exception)]
    assert len(successes) == 1 and len(failures) == 1, results
    assert failures[0].available == 0
    assert (
        scalar(migrated_engine, "SELECT available_qty FROM inventory WHERE product_id = 'CC-P1'")
        == 0
    )
    assert (
        scalar(migrated_engine, "SELECT on_hand_qty FROM inventory WHERE product_id = 'CC-P1'") == 0
    )
    assert (
        scalar(
            migrated_engine,
            "SELECT count(*) FROM orders WHERE status = 'confirmed' AND order_id LIKE 'CC-%'",
        )
        == 1
    )
    assert (
        scalar(
            migrated_engine,
            "SELECT count(*) FROM orders "
            "WHERE status = 'pending_confirmation' AND order_id LIKE 'CC-%'",
        )
        == 1
    )
    assert (
        scalar(migrated_engine, "SELECT count(*) FROM order_allocations WHERE order_id LIKE 'CC-%'")
        == 1
    )


def test_same_order_confirmed_twice_at_once(migrated_engine: Engine, committed_data):
    committed_data(5, ["cc-a"])

    results = run_together(migrated_engine, [("cc-a", "CC-ORDER-0"), ("cc-a", "CC-ORDER-0")])

    rejected = [r for r in results if isinstance(r, OrderNotPending)]
    successes = [r for r in results if not isinstance(r, Exception)]
    assert len(successes) == 1 and len(rejected) == 1, results
    assert (
        scalar(migrated_engine, "SELECT available_qty FROM inventory WHERE product_id = 'CC-P1'")
        == 4
    )
    assert (
        scalar(migrated_engine, "SELECT on_hand_qty FROM inventory WHERE product_id = 'CC-P1'") == 4
    )
    assert (
        scalar(migrated_engine, "SELECT count(*) FROM order_allocations WHERE order_id LIKE 'CC-%'")
        == 1
    )
