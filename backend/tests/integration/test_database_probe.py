"""The health check answers "down" instead of hanging when the database does not."""

import time

import pytest
from sqlalchemy import Engine

from app.adapters.persistence import database_probe
from app.adapters.persistence.database_probe import SqlAlchemyDatabaseProbe

pytestmark = pytest.mark.integration


def test_the_probe_reports_the_database_available(migrated_engine: Engine) -> None:
    assert SqlAlchemyDatabaseProbe(migrated_engine).is_available() is True


def test_a_slow_database_is_reported_down_within_the_timeout(
    migrated_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(database_probe, "PROBE_STATEMENT", "SELECT pg_sleep(10)")
    probe = SqlAlchemyDatabaseProbe(migrated_engine, timeout_seconds=0.3)

    started = time.monotonic()
    available = probe.is_available()

    assert available is False
    assert time.monotonic() - started < 3
