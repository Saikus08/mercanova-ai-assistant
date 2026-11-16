"""EmbeddingModel port implemented over the Ollama HTTP API (POST /api/embed)."""

import httpx

from app.adapters.persistence.orm.catalog import EMBEDDING_DIMENSIONS
from app.domain.search import SearchUnavailable


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

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            response = self._client.post("/api/embed", json={"model": self._model, "input": texts})
            response.raise_for_status()
            embeddings = response.json().get("embeddings")
        except httpx.TimeoutException as error:
            raise SearchUnavailable("The embedding request timed out") from error
        except httpx.HTTPStatusError as error:
            status = error.response.status_code
            raise SearchUnavailable(f"Ollama answered HTTP {status}") from error
        except (httpx.HTTPError, ValueError, AttributeError) as error:
            raise SearchUnavailable(f"Could not reach Ollama: {error}") from error

        if not isinstance(embeddings, list):
            raise SearchUnavailable("Ollama response has no embeddings")
        if len(embeddings) != len(texts):
            raise SearchUnavailable(
                f"Ollama returned {len(embeddings)} vectors for {len(texts)} texts"
            )
        if any(len(vector) != EMBEDDING_DIMENSIONS for vector in embeddings):
            raise SearchUnavailable(
                f"Unexpected embedding dimension, expected {EMBEDDING_DIMENSIONS}"
            )
        return embeddings
