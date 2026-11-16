"""One place that turns exceptions into the contract's error body."""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.adapters.api.session import InvalidSessionId, MissingSession
from app.domain.cart import (
    InsufficientStock,
    InvalidQuantity,
    ItemNotInCart,
    ProductInactive,
)
from app.domain.catalog import InvalidComparison, ProductNotFound

logger = logging.getLogger(__name__)


_HTTP_ERRORS = {
    404: ("NOT_FOUND", "El recurso no existe."),
    405: ("METHOD_NOT_ALLOWED", "Método no permitido."),
}


def error_response(
    status_code: int, code: str, message: str, details: dict[str, Any] | None = None
) -> JSONResponse:
    body = {"error": {"code": code, "message": message, "details": details}}
    return JSONResponse(status_code=status_code, content=body)


def _product_not_found(_: Request, error: Exception) -> JSONResponse:
    assert isinstance(error, ProductNotFound)
    return error_response(
        404, "PRODUCT_NOT_FOUND", "El producto no existe.", {"product_id": error.product_id}
    )


def _invalid_comparison(_: Request, error: Exception) -> JSONResponse:
    return error_response(400, "VALIDATION_ERROR", "Se pueden comparar entre 2 y 4 productos.")


def _item_not_in_cart(_: Request, error: Exception) -> JSONResponse:
    assert isinstance(error, ItemNotInCart)
    return error_response(
        404,
        "PRODUCT_NOT_FOUND",
        "El producto no está en el carrito.",
        {"product_id": error.product_id},
    )


def _insufficient_stock(_: Request, error: Exception) -> JSONResponse:
    assert isinstance(error, InsufficientStock)
    available = error.available
    message = (
        "Solo hay 1 unidad disponible."
        if available == 1
        else f"Solo hay {available} unidades disponibles."
    )
    return error_response(
        409,
        "INSUFFICIENT_STOCK",
        message,
        {"product_id": error.product_id, "available_qty": available},
    )


def _product_inactive(_: Request, error: Exception) -> JSONResponse:
    assert isinstance(error, ProductInactive)
    return error_response(
        409, "PRODUCT_INACTIVE", "El producto ya no se vende.", {"product_id": error.product_id}
    )


def _invalid_quantity(_: Request, error: Exception) -> JSONResponse:
    return error_response(
        400,
        "VALIDATION_ERROR",
        "Los datos enviados no son válidos.",
        {"errors": [{"field": "quantity", "message": str(error)}]},
    )


def _missing_session(_: Request, error: Exception) -> JSONResponse:
    return error_response(
        400, "MISSING_SESSION", "Falta el identificador de sesión (encabezado X-Session-Id)."
    )


def _invalid_session_id(_: Request, error: Exception) -> JSONResponse:
    return error_response(
        400,
        "VALIDATION_ERROR",
        "El identificador de sesión no es válido.",
        {"errors": [{"field": "X-Session-Id", "message": "Must be 1 to 64 characters."}]},
    )


def _validation_error(_: Request, error: Exception) -> JSONResponse:
    assert isinstance(error, RequestValidationError)
    problems = [
        {"field": ".".join(str(part) for part in e["loc"][1:]), "message": e["msg"]}
        for e in error.errors()
    ]
    return error_response(
        400, "VALIDATION_ERROR", "Los datos enviados no son válidos.", {"errors": problems}
    )


def _http_error(_: Request, error: Exception) -> JSONResponse:
    assert isinstance(error, StarletteHTTPException)
    code, message = _HTTP_ERRORS.get(
        error.status_code, ("HTTP_ERROR", "No se pudo procesar el pedido.")
    )
    response = error_response(error.status_code, code, message)
    if error.headers:
        response.headers.update(error.headers)
    return response


def _unexpected_error(_: Request, error: Exception) -> JSONResponse:
    logger.exception("Unhandled error", exc_info=error)
    return error_response(500, "INTERNAL_ERROR", "Ocurrió un error inesperado.")


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ProductNotFound, _product_not_found)
    app.add_exception_handler(InvalidComparison, _invalid_comparison)
    app.add_exception_handler(ItemNotInCart, _item_not_in_cart)
    app.add_exception_handler(InsufficientStock, _insufficient_stock)
    app.add_exception_handler(ProductInactive, _product_inactive)
    app.add_exception_handler(InvalidQuantity, _invalid_quantity)
    app.add_exception_handler(MissingSession, _missing_session)
    app.add_exception_handler(InvalidSessionId, _invalid_session_id)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(StarletteHTTPException, _http_error)
    app.add_exception_handler(Exception, _unexpected_error)
