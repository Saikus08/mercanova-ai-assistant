"""Cart endpoints. Every route needs the X-Session-Id header."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.adapters.api.session import get_session_id
from app.adapters.persistence.cart_repository import SqlAlchemyCartRepository
from app.adapters.persistence.session import get_session
from app.application import cart as use_cases
from app.application.ports import CartRepository
from app.domain.cart import Cart

router = APIRouter(prefix="/api/cart", tags=["cart"])


class CartItemResponse(BaseModel):
    product_id: str
    name: str
    image_url: str | None
    unit_price: float
    quantity: int
    line_total: float
    available_qty: int


class CartResponse(BaseModel):
    items: list[CartItemResponse]
    item_count: int
    total: float
    currency: str


# The quantity range is a domain rule (400 VALIDATION_ERROR), so it is not repeated here.
class AddItemRequest(BaseModel):
    product_id: str
    quantity: int


class SetQuantityRequest(BaseModel):
    quantity: int


def get_cart_repository(session: Session = Depends(get_session)) -> CartRepository:
    return SqlAlchemyCartRepository(session)


def _cart(cart: Cart) -> CartResponse:
    return CartResponse(
        items=[
            CartItemResponse(
                product_id=line.product_id,
                name=line.name,
                image_url=line.image_url,
                unit_price=round(float(line.unit_price), 2),
                quantity=line.quantity,
                line_total=round(float(line.line_total), 2),
                available_qty=line.available_qty,
            )
            for line in cart.items
        ],
        item_count=cart.item_count,
        total=round(float(cart.total), 2),
        currency=cart.currency,
    )


@router.get("", response_model=CartResponse)
def get_cart(
    session_id: str = Depends(get_session_id),
    repository: CartRepository = Depends(get_cart_repository),
) -> CartResponse:
    return _cart(use_cases.view_cart(repository, session_id))


@router.post("/items", response_model=CartResponse)
def add_item(
    body: AddItemRequest,
    session_id: str = Depends(get_session_id),
    repository: CartRepository = Depends(get_cart_repository),
) -> CartResponse:
    return _cart(use_cases.add_item(repository, session_id, body.product_id, body.quantity))


@router.patch("/items/{product_id}", response_model=CartResponse)
def set_quantity(
    product_id: str,
    body: SetQuantityRequest,
    session_id: str = Depends(get_session_id),
    repository: CartRepository = Depends(get_cart_repository),
) -> CartResponse:
    return _cart(use_cases.set_quantity(repository, session_id, product_id, body.quantity))


@router.delete("/items/{product_id}", response_model=CartResponse)
def remove_item(
    product_id: str,
    session_id: str = Depends(get_session_id),
    repository: CartRepository = Depends(get_cart_repository),
) -> CartResponse:
    return _cart(use_cases.remove_item(repository, session_id, product_id))


@router.delete("", response_model=CartResponse)
def clear_cart(
    session_id: str = Depends(get_session_id),
    repository: CartRepository = Depends(get_cart_repository),
) -> CartResponse:
    return _cart(use_cases.clear_cart(repository, session_id))
