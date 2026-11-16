"""Purchase rules and checkout use cases with fakes (no database)."""

from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.application.checkout import (
    cancel_order,
    checkout,
    confirm_order,
    get_order,
    list_orders,
)
from app.domain.cart import CartLine, InsufficientStock, ProductInactive, ProductStockInfo
from app.domain.order import DeliveryMethod, OrderStatus
from app.domain.purchase import (
    Allocation,
    CartEmpty,
    ConfirmationPlan,
    Customer,
    Delivery,
    DeliveryOption,
    InvalidCheckout,
    Order,
    OrderLine,
    PriceChanged,
    StockRow,
    check_stock,
    plan_confirmation,
    validate_checkout,
)

SESSION = "session-a"
CUSTOMER = Customer("Ana Pérez", "ana@example.com", "Av. 18 de Julio 1234")
PICKUP_W1 = Delivery(DeliveryMethod.PICKUP, "W1")
SHIPPING = Delivery(DeliveryMethod.SHIPPING, None)
OPTIONS = [DeliveryOption("W1", True, True), DeliveryOption("W2", True, False)]


def row(product_id: str, warehouse_id: str, qty: int, shipping: bool = True) -> StockRow:
    return StockRow(product_id, warehouse_id, qty, shipping)


def order(
    delivery: Delivery, lines: dict[str, tuple[str, int]], status=OrderStatus.PENDING_CONFIRMATION
) -> Order:
    items = [
        OrderLine(pid, f"Product {pid}", Decimal(price), qty, Decimal(price) * qty)
        for pid, (price, qty) in lines.items()
    ]
    return Order(
        order_id="ORD-20261112-0001",
        status=status,
        created_at=datetime(2026, 11, 12, tzinfo=UTC),
        confirmed_at=None,
        customer=CUSTOMER,
        delivery=delivery,
        items=items,
        total=sum((i.line_total for i in items), Decimal("0")),
        currency="USD",
    )


def allocations(plan: ConfirmationPlan) -> list[tuple[str, str, int]]:
    return [(a.product_id, a.warehouse_id, a.quantity) for a in plan.allocations]


# --- plan_confirmation ---


def test_pickup_takes_everything_from_the_chosen_warehouse():
    rows = [row("P1", "W1", 5), row("P1", "W2", 9, shipping=False)]
    plan = plan_confirmation(order(PICKUP_W1, {"P1": ("10.00", 4)}), {"P1": Decimal("10.00")}, rows)
    assert allocations(plan) == [("P1", "W1", 4)]


def test_pickup_ignores_stock_in_other_warehouses():
    rows = [row("P1", "W1", 2), row("P1", "W2", 9)]
    with pytest.raises(InsufficientStock) as error:
        plan_confirmation(order(PICKUP_W1, {"P1": ("10.00", 3)}), {"P1": Decimal("10.00")}, rows)
    assert (error.value.product_id, error.value.available) == ("P1", 2)


def test_shipping_takes_from_the_warehouse_with_most_stock_first():
    rows = [row("P1", "W1", 3), row("P1", "W2", 8)]
    plan = plan_confirmation(order(SHIPPING, {"P1": ("10.00", 5)}), {"P1": Decimal("10.00")}, rows)
    assert allocations(plan) == [("P1", "W2", 5)]


def test_shipping_spreads_across_warehouses_when_one_is_not_enough():
    rows = [row("P1", "W1", 3), row("P1", "W2", 4), row("P1", "W3", 1)]
    plan = plan_confirmation(order(SHIPPING, {"P1": ("10.00", 6)}), {"P1": Decimal("10.00")}, rows)
    assert allocations(plan) == [("P1", "W2", 4), ("P1", "W1", 2)]


def test_shipping_tie_is_broken_by_warehouse_id():
    rows = [row("P1", "W2", 3), row("P1", "W1", 3)]
    plan = plan_confirmation(order(SHIPPING, {"P1": ("10.00", 4)}), {"P1": Decimal("10.00")}, rows)
    assert allocations(plan) == [("P1", "W1", 3), ("P1", "W2", 1)]


def test_shipping_ignores_warehouses_without_shipping():
    rows = [row("P1", "W1", 2), row("P1", "W2", 50, shipping=False)]
    with pytest.raises(InsufficientStock) as error:
        plan_confirmation(order(SHIPPING, {"P1": ("10.00", 5)}), {"P1": Decimal("10.00")}, rows)
    assert error.value.available == 2


def test_stock_is_checked_before_price():
    rows = [row("P1", "W1", 1)]
    with pytest.raises(InsufficientStock):
        plan_confirmation(order(PICKUP_W1, {"P1": ("10.00", 2)}), {"P1": Decimal("99.00")}, rows)


def test_price_change_reports_old_and_new_price():
    rows = [row("P1", "W1", 5)]
    with pytest.raises(PriceChanged) as error:
        plan_confirmation(order(PICKUP_W1, {"P1": ("10.00", 2)}), {"P1": Decimal("12.50")}, rows)
    assert error.value.product_id == "P1"
    assert (error.value.old_price, error.value.new_price) == (Decimal("10.00"), Decimal("12.50"))


def test_product_without_current_price_is_not_for_sale():
    with pytest.raises(ProductInactive):
        plan_confirmation(order(PICKUP_W1, {"P1": ("10.00", 1)}), {}, [row("P1", "W1", 5)])


def test_matching_price_and_stock_produce_a_plan_for_every_line():
    rows = [row("P1", "W1", 5), row("P2", "W1", 5), row("P2", "W2", 9)]
    prices = {"P1": Decimal("10.00"), "P2": Decimal("2.00")}
    plan = plan_confirmation(order(SHIPPING, {"P1": ("10.00", 1), "P2": ("2.00", 6)}), prices, rows)
    assert allocations(plan) == [("P1", "W1", 1), ("P2", "W2", 6)]


def test_check_stock_reports_the_first_short_line():
    rows = [row("P1", "W1", 5), row("P2", "W1", 1)]
    with pytest.raises(InsufficientStock) as error:
        check_stock([("P1", 2), ("P2", 3)], PICKUP_W1, rows)
    assert (error.value.product_id, error.value.requested, error.value.available) == ("P2", 3, 1)


# --- validation ---


def problems(customer: Customer, delivery: Delivery, options=OPTIONS) -> dict[str, str]:
    with pytest.raises(InvalidCheckout) as error:
        validate_checkout(customer, delivery, options)
    return dict(error.value.errors)


def test_valid_checkout_is_normalized():
    customer, delivery = validate_checkout(
        Customer("  Ana  ", " ana@example.com ", " Calle 1 "),
        Delivery(DeliveryMethod.SHIPPING, "W1"),
        OPTIONS,
    )
    assert customer == Customer("Ana", "ana@example.com", "Calle 1")
    assert delivery == SHIPPING  # warehouse_id is ignored for shipping


@pytest.mark.parametrize("field", ["name", "email", "address"])
def test_blank_customer_fields_are_rejected(field):
    values = {"name": "Ana", "email": "ana@example.com", "address": "Calle 1", field: "   "}
    assert f"customer.{field}" in problems(Customer(**values), SHIPPING)


@pytest.mark.parametrize("email", ["ana", "ana@", "@example.com", "ana@example", "a b@c.com"])
def test_invalid_email_is_rejected(email):
    assert "customer.email" in problems(Customer("Ana", email, "Calle 1"), SHIPPING)


@pytest.mark.parametrize(("field", "limit"), [("name", 120), ("email", 254), ("address", 300)])
def test_too_long_fields_are_rejected(field, limit):
    values = {"name": "Ana", "email": "ana@example.com", "address": "Calle 1"}
    values[field] = "a" * (limit + 1) if field != "email" else "a" * limit + "@example.com"
    assert f"customer.{field}" in problems(Customer(**values), SHIPPING)


def test_pickup_requires_a_warehouse():
    assert "delivery.warehouse_id" in problems(CUSTOMER, Delivery(DeliveryMethod.PICKUP, None))


@pytest.mark.parametrize("warehouse_id", ["NOPE", "  "])
def test_pickup_requires_an_existing_warehouse(warehouse_id):
    delivery = Delivery(DeliveryMethod.PICKUP, warehouse_id)
    assert "delivery.warehouse_id" in problems(CUSTOMER, delivery)


def test_pickup_requires_a_pickup_enabled_warehouse():
    options = [DeliveryOption("W1", False, True)]
    assert "delivery.warehouse_id" in problems(CUSTOMER, PICKUP_W1, options)


def test_shipping_requires_a_shipping_enabled_warehouse():
    options = [DeliveryOption("W1", True, False)]
    assert "delivery.method" in problems(CUSTOMER, SHIPPING, options)


def test_problems_never_contain_the_submitted_values():
    customer = Customer("", "secret@mail", "Secret Street 1")
    text = repr(problems(customer, SHIPPING))
    assert "secret" not in text.lower()


def test_customer_repr_hides_personal_data():
    assert "ana@example.com" not in repr(CUSTOMER)


# --- checkout use case ---


class FakeCartRepository:
    def __init__(self) -> None:
        self.lines: list[CartLine] = []
        self.info: dict[str, ProductStockInfo] = {}

    def put(self, product_id: str, price: str, qty: int, active: bool = True, has_price=True):
        self.lines.append(
            CartLine(product_id, f"Product {product_id}", None, Decimal(price), qty, 0)
        )
        self.info[product_id] = ProductStockInfo(product_id, "n", active, has_price, 0)

    def get_lines(self, session_id: str) -> list[CartLine]:
        return list(self.lines)

    def product_stock_info(self, product_id: str) -> ProductStockInfo | None:
        return self.info.get(product_id)


class FakeOrderRepository:
    def __init__(self) -> None:
        self.stock: list[StockRow] = []
        self.created: list[tuple] = []

    def delivery_options(self) -> list[DeliveryOption]:
        return OPTIONS

    def stock_rows(self, product_ids: list[str]) -> list[StockRow]:
        return [r for r in self.stock if r.product_id in product_ids]

    def create(self, session_id, customer, delivery, items, total) -> Order:
        self.created.append((session_id, customer, delivery, items, total))
        return Order(
            "ORD-20261112-0001",
            OrderStatus.PENDING_CONFIRMATION,
            datetime(2026, 11, 12, tzinfo=UTC),
            None,
            customer,
            delivery,
            items,
            total,
            "USD",
        )

    def confirm(
        self, order_id: str, session_id: str, decide: Callable[..., ConfirmationPlan]
    ) -> Order:
        self.confirmed = (order_id, session_id, decide)
        return order(PICKUP_W1, {"P1": ("10.00", 1)}, OrderStatus.CONFIRMED)

    def cancel(self, order_id: str, session_id: str) -> Order:
        self.cancelled = (order_id, session_id)
        return order(PICKUP_W1, {"P1": ("10.00", 1)}, OrderStatus.CANCELLED)

    def list_for_session(self, session_id: str) -> list[Order]:
        self.listed = session_id
        return [order(PICKUP_W1, {"P1": ("10.00", 1)})]

    def get(self, order_id: str, session_id: str) -> Order:
        self.fetched = (order_id, session_id)
        return order(PICKUP_W1, {"P1": ("10.00", 1)})


@pytest.fixture
def carts() -> FakeCartRepository:
    repository = FakeCartRepository()
    repository.put("P1", "100.00", 2)
    repository.put("P2", "19.99", 3)
    return repository


@pytest.fixture
def orders() -> FakeOrderRepository:
    repository = FakeOrderRepository()
    repository.stock = [row("P1", "W1", 5), row("P2", "W1", 3), row("P2", "W2", 10, shipping=False)]
    return repository


def test_checkout_copies_current_price_and_name(carts, orders):
    created = checkout(carts, orders, SESSION, CUSTOMER, PICKUP_W1)
    assert created.status is OrderStatus.PENDING_CONFIRMATION
    assert [
        (i.product_id, i.name, i.unit_price, i.quantity, i.line_total) for i in created.items
    ] == [
        ("P1", "Product P1", Decimal("100.00"), 2, Decimal("200.00")),
        ("P2", "Product P2", Decimal("19.99"), 3, Decimal("59.97")),
    ]
    assert created.total == Decimal("259.97")
    assert orders.created[0][0] == SESSION


def test_checkout_does_not_clear_the_cart(carts, orders):
    checkout(carts, orders, SESSION, CUSTOMER, PICKUP_W1)
    assert len(carts.lines) == 2


def test_checkout_with_empty_cart(carts, orders):
    carts.lines.clear()
    with pytest.raises(CartEmpty):
        checkout(carts, orders, SESSION, CUSTOMER, PICKUP_W1)
    assert orders.created == []


@pytest.mark.parametrize("kwargs", [{"active": False}, {"has_price": False}])
def test_checkout_rejects_products_not_for_sale(carts, orders, kwargs):
    carts.put("P3", "1.00", 1, **kwargs)
    with pytest.raises(ProductInactive) as error:
        checkout(carts, orders, SESSION, CUSTOMER, PICKUP_W1)
    assert error.value.product_id == "P3"
    assert orders.created == []


def test_checkout_pickup_checks_the_chosen_warehouse(carts, orders):
    with pytest.raises(InsufficientStock) as error:
        checkout(carts, orders, SESSION, CUSTOMER, Delivery(DeliveryMethod.PICKUP, "W2"))
    assert error.value.available == 0
    assert orders.created == []


def test_checkout_shipping_sums_shipping_warehouses(carts, orders):
    carts.put("P3", "5.00", 4)
    orders.stock += [row("P3", "W1", 2), row("P3", "W2", 2)]
    created = checkout(carts, orders, SESSION, CUSTOMER, SHIPPING)
    assert created.delivery == SHIPPING


def test_checkout_insufficient_stock_reports_available(carts, orders):
    carts.put("P3", "5.00", 4)
    orders.stock += [row("P3", "W1", 2), row("P3", "W2", 5, shipping=False)]
    with pytest.raises(InsufficientStock) as error:
        checkout(carts, orders, SESSION, CUSTOMER, SHIPPING)
    assert (error.value.product_id, error.value.available) == ("P3", 2)
    assert orders.created == []


def test_checkout_validates_customer_and_delivery(carts, orders):
    with pytest.raises(InvalidCheckout):
        checkout(
            carts, orders, SESSION, Customer("", "x", "y"), Delivery(DeliveryMethod.PICKUP, None)
        )
    assert orders.created == []


def test_confirm_delegates_the_decision_to_the_domain(orders):
    confirmed = confirm_order(orders, SESSION, "ORD-1")
    assert confirmed.status is OrderStatus.CONFIRMED
    assert orders.confirmed == ("ORD-1", SESSION, plan_confirmation)


def test_cancel_delegates_to_the_repository(orders):
    assert cancel_order(orders, SESSION, "ORD-1").status is OrderStatus.CANCELLED
    assert orders.cancelled == ("ORD-1", SESSION)


def test_allocation_is_a_value_object():
    assert Allocation("P1", "W1", 2) == Allocation("P1", "W1", 2)


# --- history ---


def test_list_orders_reads_only_the_callers_session(orders):
    listed = list_orders(orders, SESSION)
    assert orders.listed == SESSION
    assert [o.order_id for o in listed] == ["ORD-20261112-0001"]


def test_get_order_passes_the_session_so_other_sessions_cannot_read_it(orders):
    get_order(orders, SESSION, "ORD-20261112-0001")
    assert orders.fetched == ("ORD-20261112-0001", SESSION)
