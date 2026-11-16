"""Ports (interfaces) that adapters implement."""

from typing import Protocol

from app.domain.catalog import (
    CategoryGroup,
    ProductDetail,
    ProductFilters,
    ProductPage,
    ProductSummary,
    SortOrder,
    Specification,
    Warehouse,
)
from app.domain.search import SearchFilters, SearchHit


class DatabaseProbe(Protocol):
    def is_available(self) -> bool:
        """Return True when the database answers a trivial query."""
        ...


class CatalogRepository(Protocol):
    """Read-only catalog access. Price and stock are read from the database on every call."""

    def list_products(
        self, filters: ProductFilters, sort: SortOrder | None, page: int, page_size: int
    ) -> ProductPage: ...

    def get_summaries(self, product_ids: list[str]) -> list[ProductSummary]:
        """Summaries for the ids that exist (active or not), in no particular order."""
        ...

    def get_detail(self, product_id: str) -> ProductDetail | None: ...

    def get_specifications(self, product_ids: list[str]) -> dict[str, list[Specification]]: ...

    def list_categories(self) -> list[CategoryGroup]: ...

    def list_warehouses(self) -> list[Warehouse]: ...


class EmbeddingModel(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]:
        """One vector per text, in order. Raises SearchUnavailable when the model fails."""
        ...


class SemanticSearch(Protocol):
    def search(
        self, vector: list[float], filters: SearchFilters, top_k: int
    ) -> list[SearchHit]:
        """Active products nearest to the vector that pass the filters, best first.

        Price and stock filters are evaluated against the database at query time.
        """
        ...
