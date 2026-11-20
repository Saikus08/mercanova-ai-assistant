"""Chat model defaults (decision 0011)."""

import pytest
from pydantic import ValidationError

from app.config import Settings


def make_settings(monkeypatch: pytest.MonkeyPatch, **env: str) -> Settings:
    for name in ("LLM_THINK", "LLM_MODEL"):
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    return Settings(database_url="postgresql+psycopg://u:p@localhost/db", _env_file=None)


def test_reasoning_mode_is_off_by_default(monkeypatch):
    assert make_settings(monkeypatch).llm_think is False


def test_default_chat_model_is_qwen3_8b(monkeypatch):
    assert make_settings(monkeypatch).llm_model == "qwen3:8b"


@pytest.mark.parametrize(("value", "expected"), [("true", True), ("false", False)])
def test_reasoning_mode_can_be_set_from_the_environment(monkeypatch, value, expected):
    assert make_settings(monkeypatch, LLM_THINK=value).llm_think is expected


def test_turn_time_budget_defaults_to_90_seconds_and_can_be_overridden(monkeypatch):
    assert make_settings(monkeypatch).agent_turn_timeout_seconds == 90.0
    assert (
        make_settings(monkeypatch, AGENT_TURN_TIMEOUT_SECONDS="45").agent_turn_timeout_seconds
        == 45.0
    )


@pytest.mark.parametrize("value", ["0", "-5"])
def test_turn_time_budget_must_be_positive(monkeypatch, value):
    with pytest.raises(ValidationError):
        make_settings(monkeypatch, AGENT_TURN_TIMEOUT_SECONDS=value)
