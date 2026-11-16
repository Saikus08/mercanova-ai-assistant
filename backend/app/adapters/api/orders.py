"""Two-step purchase endpoints. Confirming and cancelling are triggered only by the user's UI."""

from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.adapters.api.cart import get_cart_repository
from app.adapters.api.session import get_session_id
from app.adapters.persistence.order_repository import SqlAlchemyOrderRepository
from app.adapters.persistence.session import get_session
from app.application import checkout as use_cases
from app.application.ports import CartRepository, OrderRepository
from app.domain.order import DeliveryMethod
from app.domain.purchase import Customer, Delivery, Order

router = APIRouter(tags=["orders"])


class CustomerBody(BaseModel):
    # Length, blank and email rules are domain rules (400 VALIDATION_ERROR).
    name: str
    email: str
    address: str


class DeliveryBody(BaseModel):
    method: Literal["pickup", "shipping"]
    warehouse_id: str | None = None


class CheckoutRequest(BaseModel):
    customer: CustomerBody
    delivery: DeliveryBody


class CustomerResponse(BaseModel):
    name: str
    email: str
    address: str


class DeliveryResponse(BaseModel):
    method: str
    warehouse_id: str | None


class OrderItemResponse(BaseModel):
    product_id: str
    name: str
    unit_price: float
    quantity: int
    line_total: float


class OrderResponse(BaseModel):
    order_id: str
    status: str
    created_at: str
    confirmed_at: str | None
    customer: CustomerResponse
    delivery: DeliveryResponse
    items: list[OrderItemResponse]
    total: float
    currency: str


def get_order_repository(session: Session = Depends(get_session)) -> OrderRepository:
    return SqlAlchemyOrderRepository(session)


def _timestamp(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _order(order: Order) -> OrderResponse:
    return OrderResponse(
        order_id=order.order_id,
        status=order.status.value,
        created_at=_timestamp(order.created_at),
        confirmed_at=_timestamp(order.confirmed_at) if order.confirmed_at else None,
        customer=CustomerResponse(
            name=order.customer.name, email=order.customer.email, address=order.customer.address
        ),
        delivery=DeliveryResponse(
            method=order.delivery.method.value, warehouse_id=order.delivery.warehouse_id
        ),
        items=[
            OrderItemResponse(
                product_id=item.product_id,
                name=item.name,
                unit_price=round(float(item.unit_price), 2),
                quantity=item.quantity,
                line_total=round(float(item.line_total), 2),
            )
            for item in order.items
        ],
        total=round(float(order.total), 2),
        currency=order.currency,
    )


@router.post("/api/checkout", response_model=OrderResponse, status_code=201)
def checkout(
    body: CheckoutRequest,
    session_id: str = Depends(get_session_id),
    carts: CartRepository = Depends(get_cart_repository),
    orders: OrderRepository = Depends(get_order_repository),
) -> OrderResponse:
    customer = Customer(body.customer.name, body.customer.email, body.customer.address)
    delivery = Delivery(DeliveryMethod(body.delivery.method), body.delivery.warehouse_id)
    return _order(use_cases.checkout(carts, orders, session_id, customer, delivery))


@router.post("/api/orders/{order_id}/confirm", response_model=OrderResponse)
def confirm_order(
    order_id: str,
    session_id: str = Depends(get_session_id),
    orders: OrderRepository = Depends(get_order_repository),
) -> OrderResponse:
    return _order(use_cases.confirm_order(orders, session_id, order_id))


@router.post("/api/orders/{order_id}/cancel", response_model=OrderResponse)
def cancel_order(
    order_id: str,
    session_id: str = Depends(get_session_id),
    orders: OrderRepository = Depends(get_order_repository),
) -> OrderResponse:
    return _order(use_cases.cancel_order(orders, session_id, order_id))
