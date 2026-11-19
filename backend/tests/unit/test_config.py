"""Chat model defaults (decision 0011)."""

import pytest

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
