"""get_service_scope releases what it opened, whichever step fails (no database, no LLM)."""

import pytest

from app.adapters.api import chat as chat_module


class Resource:
    def __init__(self, name: str, log: list[str], *_: object, **__: object) -> None:
        self._name = name
        self._log = log

    def close(self) -> None:
        self._log.append(f"close {self._name}")


@pytest.fixture
def log(monkeypatch) -> list[str]:
    events: list[str] = []
    session = Resource("session", events)
    monkeypatch.setattr(chat_module, "get_session_factory", lambda: lambda: session)
    monkeypatch.setattr(chat_module, "build_chat_service", lambda *args: "service")
    return events


def install(monkeypatch, log, model=None, embedder=None) -> None:
    def make(name, failure):
        def build(*args, **kwargs):
            if failure:
                raise failure
            return Resource(name, log)

        return build

    monkeypatch.setattr(chat_module, "OllamaChat", make("model", model))
    monkeypatch.setattr(chat_module, "OllamaEmbeddings", make("embedder", embedder))


def test_everything_is_closed_in_reverse_order_after_the_turn(monkeypatch, log) -> None:
    install(monkeypatch, log)

    with chat_module.get_service_scope()() as service:
        assert service == "service"

    assert log == ["close embedder", "close model", "close session"]


def test_the_session_is_closed_when_the_model_cannot_be_built(monkeypatch, log) -> None:
    install(monkeypatch, log, model=RuntimeError("no model"))

    with pytest.raises(RuntimeError), chat_module.get_service_scope()():
        pytest.fail("the scope must not yield when the model cannot be built")

    assert log == ["close session"]


def test_the_model_and_the_session_are_closed_when_the_embedder_cannot_be_built(
    monkeypatch, log
) -> None:
    install(monkeypatch, log, embedder=RuntimeError("no embedder"))

    with pytest.raises(RuntimeError), chat_module.get_service_scope()():
        pytest.fail("the scope must not yield when the embedder cannot be built")

    assert log == ["close model", "close session"]
