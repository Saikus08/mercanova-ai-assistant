"""Hybrid semantic search and the embedding indexer against PostgreSQL with fake vectors."""

from decimal import Decimal

import pytest
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.adapters.persistence.embedding_indexer import EmbeddingIndexer
from app.adapters.persistence.orm.catalog import (
    EMBEDDING_DIMENSIONS,
    Brand,
    Category,
    Product,
    ProductEmbedding,
)
from app.adapters.persistence.orm.stock import Inventory, Price, Warehouse
from app.adapters.persistence.semantic_search_repository import SqlAlchemySemanticSearch
from app.domain.search import SearchFilters

pytestmark = pytest.mark.integration

MODEL = "fake-model"


def vec(*weights: tuple[int, float]) -> list[float]:
    """Sparse 768-dim vector: ``vec((0, 1.0), (1, 0.5))`` has those components, rest zero."""
    values = [0.0] * EMBEDDING_DIMENSIONS
    for index, weight in weights:
        values[index] = weight
    return values


# Query points at axis 0 and a little at axis 1, so P1 > P2 > the rest (tied at 0).
QUERY = vec((0, 1.0), (1, 0.5))

PRODUCTS = [
    # id, name, brand, (category, subcategory, subcategory_id), price, stock, active
    ("P1", "Vision 24", "B1", ("Monitors", "Gaming", "SC-GAM"), "300", 5, True),
    ("P2", "Office 27", "B1", ("Monitors", "Office", "SC-OFF"), "200", 0, True),
    ("P3", "Buds", "B2", ("Audio", "Headphones", "SC-HEA"), "50", 7, True),
    ("P4", "Old Monitor", "B2", ("Monitors", "Gaming", "SC-GAM"), "100", 9, False),
    ("P5", "Studio Cans", "B2", ("Audio", "Headphones", "SC-HEA"), "150", 2, True),
]


@pytest.fixture(autouse=True)
def catalog(db_session: Session) -> None:
    db_session.add_all(
        [
            Brand(brand_id="B1", brand_name="Flux"),
            Brand(brand_id="B2", brand_name="Orbit"),
            Category(
                subcategory_id="SC-GAM",
                subcategory_name="Gaming",
                category_id="C-MON",
                category_name="Monitors",
            ),
            Category(
                subcategory_id="SC-OFF",
                subcategory_name="Office",
                category_id="C-MON",
                category_name="Monitors",
            ),
            Category(
                subcategory_id="SC-HEA",
                subcategory_name="Headphones",
                category_id="C-AUD",
                category_name="Audio",
            ),
            Warehouse(warehouse_id="W1", warehouse_name="Centro"),
            Warehouse(warehouse_id="W2", warehouse_name="Costa"),
        ]
    )
    db_session.flush()
    for index, (pid, name, brand, sub, price, stock, active) in enumerate(PRODUCTS):
        category, subcategory, subcategory_id = sub
        db_session.add(
            Product(
                product_id=pid,
                sku=f"SKU-{pid}",
                name=name,
                brand_id=brand,
                subcategory_id=subcategory_id,
                category_name=category,
                subcategory_name=subcategory,
                short_description=f"About {name}",
                active=active,
            )
        )
        db_session.flush()
        db_session.add(
            Price(
                product_id=pid,
                currency="USD",
                list_price=Decimal(price),
                current_price=Decimal(price),
            )
        )
        # Stock split across two warehouses to prove the quantity is summed.
        if stock:
            db_session.add_all(
                Inventory(
                    product_id=pid, warehouse_id=warehouse, on_hand_qty=qty, available_qty=qty
                )
                for warehouse, qty in (("W1", stock // 2), ("W2", stock - stock // 2))
            )
        axis = {"P1": [(0, 1.0)], "P2": [(1, 1.0)]}.get(pid, [(10 + index, 1.0)])
        db_session.add(
            ProductEmbedding(
                product_id=pid, content=f"Name: {name}", embedding=vec(*axis), model=MODEL
            )
        )
    db_session.flush()


def ids(hits) -> list[str]:
    return [hit.product_id for hit in hits]


def test_search_orders_hits_by_similarity_when_vectors_differ(db_session: Session):
    hits = SqlAlchemySemanticSearch(db_session).search(QUERY, SearchFilters(), 5)

    # P4 is inactive; P3 and P5 are orthogonal to the query and tie, so product_id decides.
    assert ids(hits) == ["P1", "P2", "P3", "P5"]
    assert hits[0].score > hits[1].score > hits[2].score
    assert hits[0].score == pytest.approx(1 / (1 + 0.25) ** 0.5)
    assert hits[2].score == pytest.approx(0.0)
    assert hits[0].name == "Vision 24"
    assert hits[0].short_description == "About Vision 24"


def test_search_limits_results_when_top_k_is_smaller_than_matches(db_session: Session):
    hits = SqlAlchemySemanticSearch(db_session).search(QUERY, SearchFilters(), 2)

    assert ids(hits) == ["P1", "P2"]


def test_search_excludes_inactive_products_when_they_are_the_nearest(db_session: Session):
    hits = SqlAlchemySemanticSearch(db_session).search(vec((13, 1.0)), SearchFilters(), 5)

    assert "P4" not in ids(hits)


@pytest.mark.parametrize(
    ("filters", "expected"),
    [
        (SearchFilters(category="audio"), ["P3", "P5"]),
        (SearchFilters(category="Monitors", subcategory="OFFICE"), ["P2"]),
        (SearchFilters(brand="flux"), ["P1", "P2"]),
        (SearchFilters(max_price=Decimal("150")), ["P3", "P5"]),
        (SearchFilters(min_price=Decimal("200")), ["P1", "P2"]),
        (SearchFilters(min_price=Decimal("100"), max_price=Decimal("200")), ["P2", "P5"]),
        (SearchFilters(in_stock=True), ["P1", "P3", "P5"]),
        (SearchFilters(in_stock=False), ["P2"]),
        (SearchFilters(brand="Orbit", in_stock=True, max_price=Decimal("100")), ["P3"]),
    ],
)
def test_search_applies_filters_when_they_are_given(db_session: Session, filters, expected):
    hits = SqlAlchemySemanticSearch(db_session).search(QUERY, filters, 5)

    assert ids(hits) == expected


def test_search_reads_price_at_query_time_when_price_changes_between_searches(
    db_session: Session,
):
    searcher = SqlAlchemySemanticSearch(db_session)
    cheap = SearchFilters(max_price=Decimal("250"))
    assert "P1" not in ids(searcher.search(QUERY, cheap, 5))

    db_session.execute(
        update(Price).where(Price.product_id == "P1").values(current_price=Decimal("199"))
    )

    assert ids(searcher.search(QUERY, cheap, 5))[0] == "P1"


def test_search_reads_stock_at_query_time_when_stock_changes_between_searches(
    db_session: Session,
):
    searcher = SqlAlchemySemanticSearch(db_session)
    assert "P2" not in ids(searcher.search(QUERY, SearchFilters(in_stock=True), 5))

    db_session.add(Inventory(product_id="P2", warehouse_id="W1", on_hand_qty=3, available_qty=3))
    db_session.flush()

    assert "P2" in ids(searcher.search(QUERY, SearchFilters(in_stock=True), 5))


def test_search_result_exposes_no_price_or_stock_when_hits_are_returned(db_session: Session):
    hit = SqlAlchemySemanticSearch(db_session).search(QUERY, SearchFilters(), 1)[0]

    assert set(vars(hit)) == {"product_id", "name", "score", "short_description"}


# --- Indexer ---------------------------------------------------------------------------------


class CountingEmbedder:
    def __init__(self) -> None:
        self.texts: list[str] = []
        self.batches: list[int] = []

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.texts.extend(texts)
        self.batches.append(len(texts))
        return [vec((len(text) % 700, 1.0)) for text in texts]


@pytest.fixture
def no_embeddings(db_session: Session) -> None:
    db_session.query(ProductEmbedding).delete()
    db_session.flush()


@pytest.mark.usefixtures("no_embeddings")
def test_indexer_embeds_every_product_when_none_is_indexed(db_session: Session):
    embedder = CountingEmbedder()

    summary = EmbeddingIndexer(db_session, embedder, MODEL).run()

    assert (summary.total, summary.embedded, summary.skipped) == (5, 5, 0)
    assert db_session.query(ProductEmbedding).count() == 5


@pytest.mark.usefixtures("no_embeddings")
def test_indexer_sends_batches_of_at_most_batch_size_when_there_are_many_products(
    db_session: Session,
):
    embedder = CountingEmbedder()

    EmbeddingIndexer(db_session, embedder, MODEL, batch_size=2).run()

    assert embedder.batches == [2, 2, 1]


@pytest.mark.usefixtures("no_embeddings")
def test_indexer_embeds_nothing_when_run_a_second_time(db_session: Session):
    EmbeddingIndexer(db_session, CountingEmbedder(), MODEL).run()
    embedder = CountingEmbedder()

    summary = EmbeddingIndexer(db_session, embedder, MODEL).run()

    assert (summary.total, summary.embedded, summary.skipped) == (5, 0, 5)
    assert embedder.texts == []


@pytest.mark.usefixtures("no_embeddings")
def test_indexer_reembeds_only_the_changed_product_when_description_changes(db_session: Session):
    EmbeddingIndexer(db_session, CountingEmbedder(), MODEL).run()
    db_session.execute(
        update(Product).where(Product.product_id == "P3").values(description="Now with ANC")
    )
    embedder = CountingEmbedder()

    summary = EmbeddingIndexer(db_session, embedder, MODEL).run()

    assert (summary.embedded, summary.skipped) == (1, 4)
    assert "Description: Now with ANC" in embedder.texts[0]
    stored = db_session.get(ProductEmbedding, "P3")
    assert stored is not None and "Now with ANC" in stored.content


@pytest.mark.usefixtures("no_embeddings")
def test_indexer_reembeds_everything_when_model_changes(db_session: Session):
    EmbeddingIndexer(db_session, CountingEmbedder(), MODEL).run()

    summary = EmbeddingIndexer(db_session, CountingEmbedder(), "other-model").run()

    assert (summary.embedded, summary.skipped) == (5, 0)
    models = db_session.scalars(select(ProductEmbedding.model).distinct()).all()
    assert list(models) == ["other-model"]


@pytest.mark.usefixtures("no_embeddings")
def test_indexer_stores_no_price_or_stock_when_building_content(db_session: Session):
    db_session.execute(
        update(Product).where(Product.product_id == "P1").values(rating=Decimal("4.9"))
    )
    EmbeddingIndexer(db_session, CountingEmbedder(), MODEL).run()

    for content in db_session.scalars(select(ProductEmbedding.content)):
        lowered = content.lower()
        assert all(word not in lowered for word in ("price", "stock", "rating", "300", "4.9"))
