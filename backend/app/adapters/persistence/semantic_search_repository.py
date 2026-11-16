"""SQLAlchemy implementation of the SemanticSearch port (pgvector).

One query ranks by cosine distance and applies the filters. Price and stock are joined in that
same query, so filters always see the current database state; neither is returned or indexed.
"""

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.adapters.persistence.orm.catalog import Brand, Product, ProductEmbedding
from app.adapters.persistence.orm.stock import Inventory, Price
from app.domain.search import SearchFilters, SearchHit

_stock = (
    select(Inventory.product_id, func.sum(Inventory.available_qty).label("qty"))
    .group_by(Inventory.product_id)
    .subquery("stock")
)
_available_qty = func.coalesce(_stock.c.qty, 0)


def _conditions(filters: SearchFilters) -> list:
    conditions = []
    if filters.category:
        conditions.append(func.lower(Product.category_name) == filters.category.lower())
    if filters.subcategory:
        conditions.append(func.lower(Product.subcategory_name) == filters.subcategory.lower())
    if filters.brand:
        conditions.append(func.lower(Brand.brand_name) == filters.brand.lower())
    if filters.min_price is not None:
        conditions.append(Price.current_price >= filters.min_price)
    if filters.max_price is not None:
        conditions.append(Price.current_price <= filters.max_price)
    if filters.in_stock is True:
        conditions.append(_available_qty > 0)
    elif filters.in_stock is False:
        conditions.append(_available_qty == 0)
    return conditions


class SqlAlchemySemanticSearch:
    def __init__(self, session: Session) -> None:
        self._session = session

    def search(
        self, vector: list[float], filters: SearchFilters, top_k: int, index_id: str
    ) -> list[SearchHit]:
        distance = ProductEmbedding.embedding.cosine_distance(vector)
        rows = self._session.execute(
            select(Product.product_id, Product.name, Product.short_description, distance)
            .join(ProductEmbedding, ProductEmbedding.product_id == Product.product_id)
            .join(Brand, Brand.brand_id == Product.brand_id)
            .outerjoin(Price, Price.product_id == Product.product_id)
            .outerjoin(_stock, _stock.c.product_id == Product.product_id)
            .where(
                Product.active.is_(True),
                ProductEmbedding.model == index_id,
                *_conditions(filters),
            )
            .order_by(distance, Product.product_id)
            .limit(top_k)
        ).all()
        return [
            SearchHit(product_id, name, _similarity(dist), short_description)
            for product_id, name, short_description, dist in rows
        ]


def _similarity(cosine_distance: float | Decimal) -> float:
    return max(0.0, min(1.0, 1.0 - float(cosine_distance)))
