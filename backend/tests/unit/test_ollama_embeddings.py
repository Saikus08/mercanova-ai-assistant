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

    result = adapter(handler).embed_documents(["a", "b"])

    assert result == [vector(0.1), vector(0.2)]
    assert len(requests) == 1
    assert requests[0].url == "http://ollama:11434/api/embed"
    assert json.loads(requests[0].content) == {
        "model": "nomic-embed-text",
        "input": ["search_document: a", "search_document: b"],
    }


def test_embed_skips_the_call_when_there_are_no_texts():
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("no request expected")

    assert adapter(handler).embed_documents([]) == []


def test_embed_raises_unavailable_when_vector_count_is_wrong():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"embeddings": [vector()]})

    with pytest.raises(SearchUnavailable, match="1 vectors for 2 texts"):
        adapter(handler).embed_documents(["a", "b"])


def test_embed_raises_unavailable_when_dimension_is_wrong():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"embeddings": [[0.1, 0.2]]})

    with pytest.raises(SearchUnavailable, match="dimension"):
        adapter(handler).embed_documents(["a"])


def test_embed_raises_unavailable_when_response_has_no_embeddings():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"error": "model not found"})

    with pytest.raises(SearchUnavailable):
        adapter(handler).embed_documents(["a"])


def test_embed_raises_unavailable_when_ollama_returns_http_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    with pytest.raises(SearchUnavailable, match="500"):
        adapter(handler).embed_documents(["a"])


def test_embed_raises_unavailable_when_request_times_out():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(SearchUnavailable, match="timed out"):
        adapter(handler).embed_documents(["a"])


def test_embed_raises_unavailable_when_connection_fails():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    with pytest.raises(SearchUnavailable):
        adapter(handler).embed_documents(["a"])


def test_embed_query_sends_query_prefix_and_returns_one_vector():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"embeddings": [vector(0.3)]})

    result = adapter(handler).embed_query("gaming monitor")

    assert result == vector(0.3)
    assert json.loads(requests[0].content) == {
        "model": "nomic-embed-text",
        "input": ["search_query: gaming monitor"],
    }


def test_embed_query_raises_unavailable_when_dimension_is_wrong():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"embeddings": [[0.1]]})

    with pytest.raises(SearchUnavailable, match="dimension"):
        adapter(handler).embed_query("x")


def test_index_id_names_the_model_and_the_prefix_scheme():
    assert adapter(lambda request: httpx.Response(200)).index_id == (
        "nomic-embed-text+task-prefix-v1"
    )


def _malformed_cases():
    good = vector()
    return {
        "non-json body": httpx.Response(200, content=b"<html>oops</html>"),
        "json list body": httpx.Response(200, json=[1, 2]),
        "embeddings is a dict": httpx.Response(200, json={"embeddings": {"a": good}}),
        "item is null": httpx.Response(200, json={"embeddings": [None]}),
        "item is a string": httpx.Response(200, json={"embeddings": ["abc"]}),
        "element is a string": httpx.Response(
            200, json={"embeddings": [["x"] + good[1:]]}
        ),
        "element is null": httpx.Response(200, json={"embeddings": [[None] + good[1:]]}),
        "element is a bool": httpx.Response(200, json={"embeddings": [[True] + good[1:]]}),
    }


@pytest.mark.parametrize("name", list(_malformed_cases()))
def test_embed_raises_unavailable_when_answer_is_malformed(name):
    response = _malformed_cases()[name]

    with pytest.raises(SearchUnavailable):
        adapter(lambda request: response).embed_documents(["a"])


def test_embed_converts_integers_to_floats_when_ollama_returns_them():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"embeddings": [[1] + [0] * (EMBEDDING_DIMENSIONS - 1)]})

    [result] = adapter(handler).embed_documents(["a"])

    assert result[0] == 1.0
    assert all(isinstance(value, float) for value in result)


def test_close_releases_the_http_client():
    embeddings = adapter(lambda request: httpx.Response(200))

    embeddings.close()

    with pytest.raises(RuntimeError):
        embeddings.embed_documents(["a"])
