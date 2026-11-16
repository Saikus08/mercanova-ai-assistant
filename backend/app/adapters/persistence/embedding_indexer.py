"""Builds and refreshes product embeddings. Runs at load time, never per query."""

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.adapters.persistence.orm.catalog import Brand, Product, ProductEmbedding
from app.application.ports import EmbeddingModel
from app.domain.search import ProductDocumentSource, build_product_document

DEFAULT_BATCH_SIZE = 32


@dataclass(frozen=True)
class IndexSummary:
    total: int
    embedded: int
    skipped: int


class EmbeddingIndexer:
    def __init__(
        self,
        session: Session,
        embedder: EmbeddingModel,
        model: str,
        batch_size: int = DEFAULT_BATCH_SIZE,
    ) -> None:
        self._session = session
        self._embedder = embedder
        self._model = model
        self._batch_size = batch_size

    def run(self) -> IndexSummary:
        """Embed products that are missing or whose content or model changed."""
        documents = self._documents()
        stored = {
            product_id: (content, model)
            for product_id, content, model in self._session.execute(
                select(
                    ProductEmbedding.product_id, ProductEmbedding.content, ProductEmbedding.model
                )
            )
        }
        pending = [
            (product_id, content)
            for product_id, content in documents.items()
            if stored.get(product_id) != (content, self._model)
        ]
        for start in range(0, len(pending), self._batch_size):
            batch = pending[start : start + self._batch_size]
            vectors = self._embedder.embed([content for _, content in batch])
            self._upsert(batch, vectors)
            self._session.commit()  # keep finished batches if a later one fails
        return IndexSummary(len(documents), len(pending), len(documents) - len(pending))

    def _documents(self) -> dict[str, str]:
        rows = self._session.execute(
            select(Product, Brand.brand_name)
            .join(Brand, Brand.brand_id == Product.brand_id)
            .order_by(Product.product_id)
        )
        return {
            product.product_id: build_product_document(
                ProductDocumentSource(
                    product_id=product.product_id,
                    name=product.name,
                    brand=brand_name,
                    category=product.category_name,
                    subcategory=product.subcategory_name,
                    short_description=product.short_description,
                    description=product.description,
                    key_features=list(product.key_features or []),
                    recommended_for=list(product.recommended_for or []),
                    not_recommended_for=list(product.not_recommended_for or []),
                    tags=list(product.tags or []),
                )
            )
            for product, brand_name in rows
        }

    def _upsert(self, batch: list[tuple[str, str]], vectors: list[list[float]]) -> None:
        statement = insert(ProductEmbedding).values(
            [
                {
                    "product_id": product_id,
                    "content": content,
                    "embedding": vector,
                    "model": self._model,
                }
                for (product_id, content), vector in zip(batch, vectors, strict=True)
            ]
        )
        self._session.execute(
            statement.on_conflict_do_update(
                index_elements=[ProductEmbedding.product_id],
                set_={
                    "content": statement.excluded.content,
                    "embedding": statement.excluded.embedding,
                    "model": statement.excluded.model,
                    "updated_at": func.now(),
                },
            )
        )
