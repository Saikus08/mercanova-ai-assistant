"""EmbeddingModel port implemented over the Ollama HTTP API (POST /api/embed)."""

import httpx

from app.adapters.persistence.orm.catalog import EMBEDDING_DIMENSIONS
from app.domain.search import SearchUnavailable

# nomic-embed-text expects a task prefix on every input (see its model card).
DOCUMENT_PREFIX = "search_document: "
QUERY_PREFIX = "search_query: "
PREFIX_SCHEME = "task-prefix-v1"


class OllamaEmbeddings:
    def __init__(
        self,
        base_url: str,
        model: str,
        timeout_seconds: float,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._model = model
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"), timeout=timeout_seconds, transport=transport
        )

    def close(self) -> None:
        self._client.close()

    @property
    def index_id(self) -> str:
        return f"{self._model}+{PREFIX_SCHEME}"

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed([DOCUMENT_PREFIX + text for text in texts])

    def embed_query(self, text: str) -> list[float]:
        [vector] = self._embed([QUERY_PREFIX + text])
        return vector

    def _embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            response = self._client.post("/api/embed", json={"model": self._model, "input": texts})
            response.raise_for_status()
            body = response.json()
        except httpx.TimeoutException as error:
            raise SearchUnavailable("The embedding request timed out") from error
        except httpx.HTTPStatusError as error:
            status = error.response.status_code
            raise SearchUnavailable(f"Ollama answered HTTP {status}") from error
        except (httpx.HTTPError, ValueError) as error:
            raise SearchUnavailable(f"Could not reach Ollama: {error}") from error
        return _parse_embeddings(body, expected=len(texts))


def _is_real_number(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _parse_embeddings(body: object, expected: int) -> list[list[float]]:
    embeddings = body.get("embeddings") if isinstance(body, dict) else None
    if not isinstance(embeddings, list):
        raise SearchUnavailable("Ollama response has no embeddings")
    if len(embeddings) != expected:
        raise SearchUnavailable(f"Ollama returned {len(embeddings)} vectors for {expected} texts")
    vectors: list[list[float]] = []
    for item in embeddings:
        if not isinstance(item, list):
            raise SearchUnavailable("Ollama returned an embedding that is not a list")
        if len(item) != EMBEDDING_DIMENSIONS:
            raise SearchUnavailable(
                f"Unexpected embedding dimension, expected {EMBEDDING_DIMENSIONS}"
            )
        if not all(_is_real_number(value) for value in item):
            raise SearchUnavailable("Ollama returned an embedding with non-numeric values")
        vectors.append([float(value) for value in item])
    return vectors
