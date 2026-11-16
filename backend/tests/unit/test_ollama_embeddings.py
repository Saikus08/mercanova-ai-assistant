"""Ollama embeddings adapter against a mocked HTTP transport (no network)."""

import json

import httpx
import pytest

from app.adapters.llm.ollama_embeddings import OllamaEmbeddings
from app.adapters.persistence.orm.catalog import EMBEDDING_DIMENSIONS
from app.domain.search import SearchUnavailable


def vector(value: float = 0.1) -> list[float]:
    return [value] * EMBEDDING_DIMENSIONS


def adapter(handler) -> OllamaEmbeddings:
    return OllamaEmbeddings(
        "http://ollama:11434",
        "nomic-embed-text",
        timeout_seconds=5,
        transport=httpx.MockTransport(handler),
    )


def test_embed_returns_vectors_in_one_call_when_ollama_answers():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"embeddings": [vector(0.1), vector(0.2)]})

    result = adapter(handler).embed(["a", "b"])

    assert result == [vector(0.1), vector(0.2)]
    assert len(requests) == 1
    assert requests[0].url == "http://ollama:11434/api/embed"
    assert json.loads(requests[0].content) == {"model": "nomic-embed-text", "input": ["a", "b"]}


def test_embed_skips_the_call_when_there_are_no_texts():
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("no request expected")

    assert adapter(handler).embed([]) == []


def test_embed_raises_unavailable_when_vector_count_is_wrong():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"embeddings": [vector()]})

    with pytest.raises(SearchUnavailable, match="1 vectors for 2 texts"):
        adapter(handler).embed(["a", "b"])


def test_embed_raises_unavailable_when_dimension_is_wrong():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"embeddings": [[0.1, 0.2]]})

    with pytest.raises(SearchUnavailable, match="dimension"):
        adapter(handler).embed(["a"])


def test_embed_raises_unavailable_when_response_has_no_embeddings():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"error": "model not found"})

    with pytest.raises(SearchUnavailable):
        adapter(handler).embed(["a"])


def test_embed_raises_unavailable_when_ollama_returns_http_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    with pytest.raises(SearchUnavailable, match="500"):
        adapter(handler).embed(["a"])


def test_embed_raises_unavailable_when_request_times_out():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(SearchUnavailable, match="timed out"):
        adapter(handler).embed(["a"])


def test_embed_raises_unavailable_when_connection_fails():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    with pytest.raises(SearchUnavailable):
        adapter(handler).embed(["a"])
