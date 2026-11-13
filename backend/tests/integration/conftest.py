"""Integration fixtures: a migrated test database and one rolled-back transaction per test."""

from collections.abc import Iterator

import pytest
from alembic import command
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from tests.integration.db_utils import (
    TEST_DATABASE_NAME,
    alembic_config,
    create_database,
    drop_database,
)


@pytest.fixture(scope="session")
def migrated_engine() -> Iterator[Engine]:
    """Fresh `mercanova_test` database migrated to head, dropped at the end of the run."""
    url = create_database(TEST_DATABASE_NAME)
    command.upgrade(alembic_config(url), "head")
    engine = create_engine(url)
    try:
        yield engine
    finally:
        engine.dispose()
        drop_database(TEST_DATABASE_NAME)


@pytest.fixture
def db_session(migrated_engine: Engine) -> Iterator[Session]:
    """Session bound to an outer transaction that is rolled back after each test.

    ``create_savepoint`` lets a test call ``session.rollback()`` (e.g. after an
    expected IntegrityError) without leaving the outer transaction.
    """
    connection = migrated_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
