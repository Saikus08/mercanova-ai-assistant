"""The engine gives up connecting to an unreachable database instead of waiting forever."""

import pytest

from app.adapters.persistence import session


def test_the_engine_has_a_connect_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}
    monkeypatch.setattr(session, "create_engine", lambda url, **kwargs: captured.update(kwargs))
    session.get_engine.cache_clear()
    try:
        session.get_engine()
    finally:
        session.get_engine.cache_clear()

    assert captured["connect_args"] == {"connect_timeout": session.CONNECT_TIMEOUT_SECONDS}
    assert 0 < session.CONNECT_TIMEOUT_SECONDS <= 10
