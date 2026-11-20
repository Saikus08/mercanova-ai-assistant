"""FastAPI application entry point."""

from fastapi import FastAPI

from app.adapters.api import cart, catalog, chat, health, orders, transcribe
from app.adapters.api.errors import register_error_handlers
from app.config import get_settings
from app.logging_config import configure_logging


def create_app() -> FastAPI:
    configure_logging(get_settings().log_level)
    app = FastAPI(title="MercaNova AI Shopping Assistant API", version="0.1.0")
    register_error_handlers(app)
    app.include_router(health.router)
    app.include_router(catalog.router)
    app.include_router(cart.router)
    app.include_router(orders.router)
    app.include_router(chat.router)
    app.include_router(transcribe.router)
    return app


app = create_app()
