"""FastAPI application entry point."""

from fastapi import FastAPI

from app.adapters.api import health


def create_app() -> FastAPI:
    app = FastAPI(title="MercaNova AI Shopping Assistant API", version="0.1.0")
    app.include_router(health.router)
    return app


app = create_app()
