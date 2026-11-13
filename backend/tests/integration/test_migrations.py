from collections.abc import Iterator

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.engine import URL

from app.adapters.persistence.orm import Base
from tests.integration.db_utils import (
    TEST_DATABASE_NAME,
    alembic_config,
    create_database,
    drop_database,
)

pytestmark = pytest.mark.integration

EXPECTED_TABLES = {
    "brands",
    "categories",
    "products",
    "product_specifications",
    "product_relations",
    "product_embeddings",
    "prices",
    "warehouses",
    "inventory",
    "carts",
    "cart_items",
    "orders",
    "order_items",
    "order_allocations",
    "conversations",
    "messages",
}

MIGRATIONS_DATABASE = f"{TEST_DATABASE_NAME}_migrations"


@pytest.fixture
def empty_database_url() -> Iterator[URL]:
    """A separate empty database, so upgrade/downgrade never disturbs other tests."""
    url = create_database(MIGRATIONS_DATABASE)
    try:
        yield url
    finally:
        drop_database(MIGRATIONS_DATABASE)


def _tables(url: URL) -> set[str]:
    engine = create_engine(url)
    try:
        return set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def _has_vector_extension(url: URL) -> bool:
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            return bool(
                connection.execute(
                    text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
                ).scalar()
            )
    finally:
        engine.dispose()


def test_upgrade_creates_all_tables_when_database_is_empty(empty_database_url: URL) -> None:
    command.upgrade(alembic_config(empty_database_url), "head")

    assert EXPECTED_TABLES <= _tables(empty_database_url)
    assert _has_vector_extension(empty_database_url)


def test_downgrade_removes_schema_and_upgrade_restores_it(empty_database_url: URL) -> None:
    config = alembic_config(empty_database_url)
    command.upgrade(config, "head")

    command.downgrade(config, "base")
    assert _tables(empty_database_url) == {"alembic_version"}
    assert not _has_vector_extension(empty_database_url)

    command.upgrade(config, "head")
    assert EXPECTED_TABLES <= _tables(empty_database_url)


def test_migrated_schema_matches_orm_models_when_at_head(migrated_engine: Engine) -> None:
    with migrated_engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"compare_type": True})
        differences = compare_metadata(context, Base.metadata)

    assert differences == []
