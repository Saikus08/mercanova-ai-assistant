"""Integration fixtures: a migrated test database and one rolled-back transaction per test."""

from collections.abc import Iterator

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from app.adapters.persistence.session import get_session
from app.main import app
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


@pytest.fixture
def client(db_session: Session) -> Iterator[TestClient]:
    """API client whose requests run inside the test's rolled-back transaction."""
    app.dependency_overrides[get_session] = lambda: db_session
    try:
        with TestClient(app, raise_server_exceptions=False) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
