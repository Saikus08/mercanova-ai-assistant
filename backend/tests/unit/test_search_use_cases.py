"""Semantic search domain rules and use case with fakes (no database, no network)."""

import pytest

from app.application.search import search_products
from app.domain.search import (
    DEFAULT_TOP_K,
    MAX_TOP_K,
    ProductDocumentSource,
    SearchFilters,
    SearchHit,
    SearchUnavailable,
    build_product_document,
)


def source(**overrides) -> ProductDocumentSource:
    values = {
        "product_id": "MN-001",
        "name": "Vision 24",
        "brand": "Flux",
        "category": "Monitors",
        "subcategory": "Gaming",
        "short_description": "24 inch gaming monitor",
        "description": "A fast QHD panel for competitive play.",
        "key_features": ["QHD", "240 Hz"],
        "recommended_for": ["gaming", "streaming"],
        "not_recommended_for": ["print design"],
        "tags": ["monitor", "esports"],
    }
    return ProductDocumentSource(**{**values, **overrides})


def test_document_includes_static_fields_when_all_are_present():
    document = build_product_document(source())

    assert document == (
        "Name: Vision 24\n"
        "Brand: Flux\n"
        "Category: Monitors\n"
        "Subcategory: Gaming\n"
        "Short description: 24 inch gaming monitor\n"
        "Description: A fast QHD panel for competitive play.\n"
        "Key features: QHD, 240 Hz\n"
        "Recommended for: gaming, streaming\n"
        "Not recommended for: print design\n"
        "Tags: monitor, esports"
    )


def test_document_never_mentions_dynamic_data():
    document = build_product_document(source()).lower()

    for word in ("price", "stock", "rating", "review"):
        assert word not in document


def test_document_is_deterministic_when_built_twice():
    assert build_product_document(source()) == build_product_document(source())


def test_document_skips_empty_fields_when_values_are_missing():
    document = build_product_document(
        source(short_description=None, description="  ", key_features=[], tags=[""])
    )

    assert "Short description" not in document
    assert "Description" not in document
    assert "Key features" not in document
    assert "Tags" not in document
    assert document.startswith("Name: Vision 24\nBrand: Flux")


class FakeEmbedder:
    def __init__(self, error: Exception | None = None) -> None:
        self.calls: list[str] = []
        self.document_calls: list[list[str]] = []
        self._error = error

    index_id = "fake+v1"

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.document_calls.append(texts)
        return [[1.0, 0.0] for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        self.calls.append(text)
        if self._error:
            raise self._error
        return [1.0, 0.0]


class FakeSearcher:
    def __init__(self) -> None:
        self.calls: list[tuple[list[float], SearchFilters, int]] = []
        self.index_ids: list[str] = []

    def search(self, vector, filters, top_k, index_id) -> list[SearchHit]:
        self.calls.append((vector, filters, top_k))
        self.index_ids.append(index_id)
        return [SearchHit("MN-001", "Vision 24", 0.9, None)]


def test_search_embeds_query_once_and_returns_hits_when_query_is_valid():
    embedder, searcher = FakeEmbedder(), FakeSearcher()
    filters = SearchFilters(category="Monitors")

    hits = search_products(embedder, searcher, "  monitor for gaming ", filters)

    assert embedder.calls == ["monitor for gaming"]
    assert embedder.document_calls == []
    assert searcher.calls == [([1.0, 0.0], filters, DEFAULT_TOP_K)]
    assert [hit.product_id for hit in hits] == ["MN-001"]


def test_search_restricts_to_the_embedder_index_id_when_searching():
    embedder, searcher = FakeEmbedder(), FakeSearcher()

    search_products(embedder, searcher, "monitor", SearchFilters())

    assert searcher.index_ids == [embedder.index_id]


@pytest.mark.parametrize("query", ["", "   ", "\n\t"])
def test_search_rejects_query_when_it_is_blank(query):
    embedder, searcher = FakeEmbedder(), FakeSearcher()

    with pytest.raises(ValueError):
        search_products(embedder, searcher, query, SearchFilters())

    assert embedder.calls == []
    assert searcher.calls == []


@pytest.mark.parametrize(
    ("requested", "expected"), [(50, MAX_TOP_K), (0, 1), (-3, 1), (3, 3), (MAX_TOP_K, MAX_TOP_K)]
)
def test_search_clamps_top_k_when_out_of_range(requested, expected):
    searcher = FakeSearcher()

    search_products(FakeEmbedder(), searcher, "monitor", SearchFilters(), top_k=requested)

    assert searcher.calls[0][2] == expected


def test_search_raises_unavailable_when_embedder_fails():
    searcher = FakeSearcher()

    with pytest.raises(SearchUnavailable):
        search_products(
            FakeEmbedder(error=ConnectionError("down")), searcher, "monitor", SearchFilters()
        )

    assert searcher.calls == []


def test_search_keeps_unavailable_error_when_embedder_raises_it():
    with pytest.raises(SearchUnavailable, match="ollama"):
        search_products(
            FakeEmbedder(error=SearchUnavailable("ollama down")),
            FakeSearcher(),
            "monitor",
            SearchFilters(),
        )


class ScoredSearcher:
    def __init__(self, scores: list[float]) -> None:
        self._scores = scores

    def search(self, vector, filters, top_k, index_id) -> list[SearchHit]:
        return [SearchHit(f"MN-{i}", f"P{i}", score, None) for i, score in enumerate(self._scores)]


def test_search_drops_hits_below_threshold_when_min_score_is_set():
    searcher = ScoredSearcher([0.9, 0.7, 0.5, 0.3])

    hits = search_products(FakeEmbedder(), searcher, "monitor", SearchFilters(), min_score=0.6)

    assert [hit.score for hit in hits] == [0.9, 0.7]


def test_search_keeps_hit_when_score_equals_threshold():
    searcher = ScoredSearcher([0.8, 0.62, 0.61])

    hits = search_products(FakeEmbedder(), searcher, "monitor", SearchFilters(), min_score=0.62)

    assert [hit.score for hit in hits] == [0.8, 0.62]


def test_search_keeps_every_hit_when_min_score_is_not_given():
    searcher = ScoredSearcher([0.9, 0.1, 0.0])

    hits = search_products(FakeEmbedder(), searcher, "monitor", SearchFilters())

    assert len(hits) == 3


def test_search_returns_empty_list_when_every_hit_is_below_threshold():
    searcher = ScoredSearcher([0.5, 0.4])

    hits = search_products(FakeEmbedder(), searcher, "monitor", SearchFilters(), min_score=0.62)

    assert hits == []
