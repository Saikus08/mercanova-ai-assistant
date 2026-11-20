"""The server writes the agent's step logs, which are INFO and would be dropped by default."""

import logging

import pytest

from app.logging_config import HANDLER_NAME, configure_logging

AGENT_LOGGER = "app.application.agent.loop"


@pytest.fixture(autouse=True)
def restore_logging():
    app_logger = logging.getLogger("app")
    before = (app_logger.level, list(app_logger.handlers))
    yield
    app_logger.setLevel(before[0])
    app_logger.handlers[:] = before[1]


def test_agent_step_logs_are_emitted_at_the_default_level():
    configure_logging("INFO")

    assert logging.getLogger(AGENT_LOGGER).isEnabledFor(logging.INFO)


def test_a_higher_level_silences_the_step_logs():
    configure_logging("WARNING")

    assert not logging.getLogger(AGENT_LOGGER).isEnabledFor(logging.INFO)
    assert logging.getLogger(AGENT_LOGGER).isEnabledFor(logging.WARNING)


def test_configuring_twice_does_not_duplicate_the_output():
    configure_logging("INFO")
    configure_logging("INFO")

    handlers = [h for h in logging.getLogger("app").handlers if h.get_name() == HANDLER_NAME]
    assert len(handlers) == 1


def test_an_unknown_level_is_rejected():
    with pytest.raises(ValueError):
        configure_logging("LOUD")


def test_the_app_configures_logging_from_the_settings(monkeypatch):
    from app.config import get_settings
    from app.main import create_app

    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    get_settings.cache_clear()
    try:
        create_app()
        assert not logging.getLogger(AGENT_LOGGER).isEnabledFor(logging.INFO)
    finally:
        get_settings.cache_clear()
