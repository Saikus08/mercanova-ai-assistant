"""Ports (interfaces) that adapters implement."""

from collections.abc import Callable
from decimal import Decimal
from typing import Any, Protocol

from app.application.agent.tool import ToolSpec
from app.domain.agent import ChatMessage, ModelReply
from app.domain.cart import CartLine, ProductStockInfo
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
from app.domain.purchase import (
    ConfirmationPlan,
    Customer,
    Delivery,
    DeliveryOption,
    Order,
    OrderLine,
    StockRow,
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


class CartRepository(Protocol):
    """Cart storage keyed by browser session. It stores product and quantity only.

    Price, name, image and stock of each line are read from the database on every call.
    Mutating methods are atomic per session; ``check`` runs under that guarantee with the
    quantity the line would hold and may raise to abort the change.
    """

    def get_lines(self, session_id: str) -> list[CartLine]:
        """Lines ordered by the time they were added, then product id."""
        ...

    def product_stock_info(self, product_id: str) -> ProductStockInfo | None: ...

    def add_quantity(
        self, session_id: str, product_id: str, quantity: int, check: Callable[[int], None]
    ) -> None:
        """Add to the line (creating it if needed) after ``check(existing + quantity)``."""
        ...

    def set_quantity(
        self, session_id: str, product_id: str, quantity: int, check: Callable[[int], None]
    ) -> bool:
        """Replace the line quantity after ``check(quantity)``. False when not in the cart."""
        ...

    def remove_item(self, session_id: str, product_id: str) -> None:
        """Remove a line; nothing happens when it is not there."""
        ...

    def clear(self, session_id: str) -> None: ...


class OrderRepository(Protocol):
    """Order storage. Confirmation is one database transaction owned by the repository."""

    def delivery_options(self) -> list[DeliveryOption]: ...

    def stock_rows(self, product_ids: list[str]) -> list[StockRow]:
        """Current stock per warehouse, read without locking."""
        ...

    def create(
        self,
        session_id: str,
        customer: Customer,
        delivery: Delivery,
        items: list[OrderLine],
        total: Decimal,
    ) -> Order:
        """Insert a pending order with the next daily order id. Touches neither stock nor cart."""
        ...

    def confirm(
        self,
        order_id: str,
        session_id: str,
        decide: Callable[[Order, dict[str, Decimal], list[StockRow]], ConfirmationPlan],
    ) -> Order:
        """Lock the order and its stock rows, apply the plan from ``decide`` and empty the cart.

        All or nothing.
        Raises OrderNotFound or OrderNotPending, and whatever ``decide`` raises (the transaction
        is rolled back).
        """
        ...

    def cancel(self, order_id: str, session_id: str) -> Order:
        """Cancel a pending order. Stock is untouched because pending orders reserve nothing."""
        ...

    def list_for_session(self, session_id: str) -> list[Order]:
        """Every order of the session in any status, newest first, with the prices paid."""
        ...

    def get(self, order_id: str, session_id: str) -> Order:
        """One order of the session. Raises OrderNotFound if it is unknown or another session's."""
        ...


class EmbeddingModel(Protocol):
    @property
    def index_id(self) -> str:
        """Identifies how vectors are produced; a change makes stored vectors stale."""
        ...

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """One vector per document, in order. Raises SearchUnavailable when the model fails."""
        ...

    def embed_query(self, text: str) -> list[float]:
        """Vector for one user query. Raises SearchUnavailable when the model fails."""
        ...


class ChatModel(Protocol):
    def chat(
        self,
        messages: list[ChatMessage],
        tools: list[ToolSpec],
        response_schema: dict[str, Any] | None = None,
    ) -> ModelReply:
        """Send the messages and the tool specs and return the model reply.

        With a ``response_schema`` the reply content must be JSON matching it and tools are not
        offered. Raises LLMUnavailable when the model cannot answer.
        """
        ...


class SemanticSearch(Protocol):
    def search(
        self, vector: list[float], filters: SearchFilters, top_k: int, index_id: str
    ) -> list[SearchHit]:
        """Active products nearest to the vector that pass the filters, best first.

        Only vectors stored with the given ``index_id`` are compared, so stale vectors from an
        older model or prefix scheme are never mixed with the query vector.

        Price and stock filters are evaluated against the database at query time.
        """
        ...
