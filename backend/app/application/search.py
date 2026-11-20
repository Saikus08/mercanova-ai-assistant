"""Semantic search use case."""

from app.application.ports import EmbeddingModel, SemanticSearch
from app.domain.search import (
    DEFAULT_TOP_K,
    MAX_TOP_K,
    MIN_TOP_K,
    InvalidSearchQuery,
    SearchFilters,
    SearchHit,
    SearchUnavailable,
)


def search_products(
    embedder: EmbeddingModel,
    searcher: SemanticSearch,
    query: str,
    filters: SearchFilters,
    top_k: int = DEFAULT_TOP_K,
    min_score: float = 0.0,
) -> list[SearchHit]:
    query = query.strip()
    if not query:
        raise InvalidSearchQuery("The search query must not be blank")
    try:
        vector = embedder.embed_query(query)
    except SearchUnavailable:
        raise
    except Exception as error:
        raise SearchUnavailable(f"Could not embed the query: {error}") from error
    hits = searcher.search(
        vector, filters, max(MIN_TOP_K, min(top_k, MAX_TOP_K)), embedder.index_id
    )
    return [hit for hit in hits if hit.score >= min_score]
