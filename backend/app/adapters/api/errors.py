"""One place that turns exceptions into the contract's error body."""

import logging
import traceback
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import StatementError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.adapters.api.session import InvalidSessionId, MissingSession
from app.domain.agent import LLMUnavailable
from app.domain.cart import (
    InsufficientStock,
    InvalidQuantity,
    ItemNotInCart,
    ProductInactive,
)
from app.domain.catalog import InvalidComparison, ProductNotFound
from app.domain.conversation import ConversationBusy, ConversationNotFound, InvalidMessage
from app.domain.purchase import (
    CartEmpty,
    InvalidCheckout,
    OrderNotFound,
    OrderNotPending,
    PriceChanged,
)
from app.domain.speech import AudioUnreadable, InvalidAudio, SpeechToTextUnavailable

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
    if available <= 0:
        message = "Este producto no tiene stock en este momento."
    elif available == 1:
        message = "Solo hay 1 unidad disponible."
    else:
        message = f"Solo hay {available} unidades disponibles."
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


def _cart_empty(_: Request, error: Exception) -> JSONResponse:
    return error_response(409, "CART_EMPTY", "El carrito está vacío.")


def _order_not_found(_: Request, error: Exception) -> JSONResponse:
    return error_response(404, "ORDER_NOT_FOUND", "La orden no existe.")


def _order_not_pending(_: Request, error: Exception) -> JSONResponse:
    return error_response(409, "ORDER_NOT_PENDING", "La orden ya fue confirmada o cancelada.")


def _price_changed(_: Request, error: Exception) -> JSONResponse:
    assert isinstance(error, PriceChanged)
    return error_response(
        409,
        "PRICE_CHANGED",
        "El precio cambió desde que armaste la orden.",
        {
            "product_id": error.product_id,
            "old_price": round(float(error.old_price), 2),
            "new_price": round(float(error.new_price), 2),
        },
    )


def _invalid_checkout(_: Request, error: Exception) -> JSONResponse:
    assert isinstance(error, InvalidCheckout)
    problems = [{"field": field, "message": message} for field, message in error.errors]
    return error_response(
        400, "VALIDATION_ERROR", "Los datos enviados no son válidos.", {"errors": problems}
    )


def _llm_unavailable(_: Request, error: Exception) -> JSONResponse:
    return error_response(
        503,
        "LLM_UNAVAILABLE",
        "El asistente no está disponible por ahora. El resto de la tienda sigue funcionando.",
    )


def _audio_unreadable(_: Request, error: Exception) -> JSONResponse:
    return error_response(
        422,
        "AUDIO_UNREADABLE",
        "No pudimos entender el audio. Probá grabarlo de nuevo o escribí tu consulta.",
    )


def _invalid_audio(_: Request, error: Exception) -> JSONResponse:
    return error_response(
        400,
        "VALIDATION_ERROR",
        "El audio no es válido: tiene que ser webm, ogg o wav, de hasta 60 segundos y 10 MB.",
        {"errors": [{"field": "audio", "message": str(error)}]},
    )


def _stt_unavailable(_: Request, error: Exception) -> JSONResponse:
    return error_response(
        503,
        "STT_UNAVAILABLE",
        "La consulta por voz no está disponible por ahora. Podés escribir tu consulta.",
    )


def _conversation_not_found(_: Request, error: Exception) -> JSONResponse:
    return error_response(404, "CONVERSATION_NOT_FOUND", "La conversación no existe.")


def _conversation_busy(_: Request, error: Exception) -> JSONResponse:
    return error_response(
        409,
        "CONVERSATION_BUSY",
        "La conversación todavía está respondiendo el mensaje anterior. "
        "Probá de nuevo en unos segundos.",
    )


def _invalid_message(_: Request, error: Exception) -> JSONResponse:
    return error_response(
        400,
        "VALIDATION_ERROR",
        "Los datos enviados no son válidos.",
        {"errors": [{"field": "message", "message": str(error)}]},
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
    if isinstance(error, StatementError):
        # Its message embeds the bound parameters, which may be customer data: log frames only.
        frames = "".join(traceback.format_tb(error.__traceback__))
        logger.error("Unhandled %s\n%s", type(error).__name__, frames)
    else:
        logger.exception("Unhandled error", exc_info=error)
    return error_response(500, "INTERNAL_ERROR", "Ocurrió un error inesperado.")


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ProductNotFound, _product_not_found)
    app.add_exception_handler(InvalidComparison, _invalid_comparison)
    app.add_exception_handler(ItemNotInCart, _item_not_in_cart)
    app.add_exception_handler(InsufficientStock, _insufficient_stock)
    app.add_exception_handler(ProductInactive, _product_inactive)
    app.add_exception_handler(InvalidQuantity, _invalid_quantity)
    app.add_exception_handler(CartEmpty, _cart_empty)
    app.add_exception_handler(OrderNotFound, _order_not_found)
    app.add_exception_handler(OrderNotPending, _order_not_pending)
    app.add_exception_handler(PriceChanged, _price_changed)
    app.add_exception_handler(InvalidCheckout, _invalid_checkout)
    app.add_exception_handler(LLMUnavailable, _llm_unavailable)
    app.add_exception_handler(AudioUnreadable, _audio_unreadable)
    app.add_exception_handler(InvalidAudio, _invalid_audio)
    app.add_exception_handler(SpeechToTextUnavailable, _stt_unavailable)
    app.add_exception_handler(ConversationNotFound, _conversation_not_found)
    app.add_exception_handler(ConversationBusy, _conversation_busy)
    app.add_exception_handler(InvalidMessage, _invalid_message)
    app.add_exception_handler(MissingSession, _missing_session)
    app.add_exception_handler(InvalidSessionId, _invalid_session_id)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(StarletteHTTPException, _http_error)
    app.add_exception_handler(Exception, _unexpected_error)
