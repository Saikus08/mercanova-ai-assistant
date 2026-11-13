"""Write a validated catalog with upserts, so loading the same dataset twice changes nothing.

Only the catalog, price and stock tables are written. Carts, orders, conversations
and embeddings are never touched. The caller owns the transaction.
"""

from collections.abc import Sequence
from itertools import batched
from typing import Any

from pydantic import BaseModel
from sqlalchemy import Table
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.adapters.dataset.catalog_parser import ParsedCatalog
from app.adapters.persistence.orm import (
    Brand,
    Category,
    Inventory,
    Price,
    Product,
    ProductRelation,
    ProductSpecification,
    Warehouse,
)

# Keeps each INSERT well below PostgreSQL's limit of 65535 bound parameters.
BATCH_SIZE = 500


def _upsert(session: Session, table: Table, records: Sequence[BaseModel], keys: list[str]) -> None:
    """INSERT ... ON CONFLICT (keys) DO UPDATE every other column of the record."""
    for batch in batched(records, BATCH_SIZE):
        rows: list[dict[str, Any]] = [record.model_dump() for record in batch]
        statement = insert(table).values(rows)
        updates = {column: statement.excluded[column] for column in rows[0] if column not in keys}
        session.execute(statement.on_conflict_do_update(index_elements=keys, set_=updates))


def load_catalog(session: Session, catalog: ParsedCatalog) -> None:
    """Upsert every valid record, parents before children (foreign key order)."""
    steps: list[tuple[Table, Sequence[BaseModel], list[str]]] = [
        (Brand.__table__, catalog.brands.records, ["brand_id"]),
        (Category.__table__, catalog.categories.records, ["subcategory_id"]),
        (Warehouse.__table__, catalog.warehouses.records, ["warehouse_id"]),
        (Product.__table__, catalog.products.records, ["product_id"]),
        (
            ProductSpecification.__table__,
            catalog.specifications.records,
            ["product_id", "attribute_group", "attribute_name"],
        ),
        (
            ProductRelation.__table__,
            catalog.relations.records,
            ["product_id", "related_product_id", "relation_type"],
        ),
        (Price.__table__, catalog.prices.records, ["product_id"]),
        (Inventory.__table__, catalog.inventory.records, ["product_id", "warehouse_id"]),
    ]
    for table, records, keys in steps:
        _upsert(session, table, records, keys)
