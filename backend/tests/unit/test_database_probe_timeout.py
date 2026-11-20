"""A database that accepts the connection and then never answers must not hang the health check."""

import threading
import time

from app.adapters.persistence.database_probe import SqlAlchemyDatabaseProbe


class FrozenEngine:
    """connect() never returns, like a pooled connection to a database that stopped answering."""

    def __init__(self) -> None:
        self.release = threading.Event()

    def connect(self):
        self.release.wait(30)
        raise RuntimeError("released by the test")


def test_a_database_that_never_answers_is_reported_down_within_the_timeout() -> None:
    engine = FrozenEngine()
    probe = SqlAlchemyDatabaseProbe(engine, timeout_seconds=0.3)  # type: ignore[arg-type]

    started = time.monotonic()
    try:
        available = probe.is_available()
    finally:
        engine.release.set()

    assert available is False
    assert time.monotonic() - started < 3
