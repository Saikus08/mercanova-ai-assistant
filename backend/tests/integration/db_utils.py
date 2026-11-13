"""Helpers to create throwaway PostgreSQL databases for integration tests.

Tests never touch the development database: each database is created on the
same server as DATABASE_URL, migrated with Alembic and dropped afterwards.
"""

import os
import re
from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url

from app.config import get_settings

BACKEND_ROOT = Path(__file__).resolve().parents[2]
TEST_DATABASE_NAME = os.environ.get("TEST_DATABASE_NAME", "mercanova_test")

_SAFE_IDENTIFIER = re.compile(r"^[a-z_][a-z0-9_]*$")


def server_url() -> URL:
    return make_url(get_settings().database_url)


def _checked_name(name: str) -> str:
    if not _SAFE_IDENTIFIER.match(name):
        raise ValueError(f"Unsafe test database name: {name!r}")
    if name == server_url().database:
        raise ValueError("Refusing to recreate the development database used by DATABASE_URL")
    return name


def create_database(name: str) -> URL:
    """Drop (if present) and create an empty database; return its URL."""
    name = _checked_name(name)
    admin = create_engine(server_url(), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as connection:
            connection.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
            connection.execute(text(f'CREATE DATABASE "{name}"'))
    finally:
        admin.dispose()
    return server_url().set(database=name)


def drop_database(name: str) -> None:
    name = _checked_name(name)
    admin = create_engine(server_url(), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as connection:
            connection.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
    finally:
        admin.dispose()


def alembic_config(url: URL) -> Config:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    # ConfigParser interpolates '%', so escape it in the rendered URL.
    rendered = url.render_as_string(hide_password=False).replace("%", "%%")
    config.set_main_option("sqlalchemy.url", rendered)
    config.attributes["configure_logger"] = False
    return config
