"""Health check without a database: the probe is replaced by a fake."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.adapters.api.health import get_database_probe
from app.application.health import check_health
from app.main import app


class FakeDatabaseProbe:
    def __init__(self, available: bool) -> None:
        self._available = available

    def is_available(self) -> bool:
        return self._available


def test_check_health_reports_db_ok_when_probe_succeeds() -> None:
    report = check_health(FakeDatabaseProbe(available=True))

    assert report.status == "ok"
    assert report.db == "ok"


def test_check_health_reports_db_down_when_probe_fails() -> None:
    report = check_health(FakeDatabaseProbe(available=False))

    # The API keeps answering so the rest of the store can degrade gracefully.
    assert report.status == "ok"
    assert report.db == "down"


@pytest.fixture
def client_with_db_down() -> Iterator[TestClient]:
    app.dependency_overrides[get_database_probe] = lambda: FakeDatabaseProbe(available=False)
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


def test_health_endpoint_reports_db_down_when_database_is_unreachable(
    client_with_db_down: TestClient,
) -> None:
    response = client_with_db_down.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": "down", "llm": "unknown", "stt": "unknown"}
