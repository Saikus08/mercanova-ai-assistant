"""FastAPI application entry point."""

from fastapi import FastAPI

from app.adapters.api import cart, catalog, health, orders
from app.adapters.api.errors import register_error_handlers


def create_app() -> FastAPI:
    app = FastAPI(title="MercaNova AI Shopping Assistant API", version="0.1.0")
    register_error_handlers(app)
    app.include_router(health.router)
    app.include_router(catalog.router)
    app.include_router(cart.router)
    app.include_router(orders.router)
    return app


app = create_app()
