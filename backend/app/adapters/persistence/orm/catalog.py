"""Catalog tables: static product content loaded from the dataset.

This content may be indexed for semantic search (RAG). Price and stock live in
``stock.py`` and are never embedded.
"""

from datetime import date, datetime
from decimal import Decimal

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.adapters.persistence.base import Base

# nomic-embed-text produces 768-dimensional vectors.
EMBEDDING_DIMENSIONS = 768


class Brand(Base):
    __tablename__ = "brands"

    brand_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    brand_name: Mapped[str] = mapped_column(Text)
    country_of_origin: Mapped[str | None] = mapped_column(Text)
    positioning: Mapped[str | None] = mapped_column(Text)


class Category(Base):
    """One row per subcategory; the parent category repeats on each row (as in the dataset)."""

    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("category_name", "subcategory_name"),)

    subcategory_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    subcategory_name: Mapped[str] = mapped_column(Text)
    category_id: Mapped[str] = mapped_column(String(16), index=True)
    category_name: Mapped[str] = mapped_column(Text)
    department: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int | None] = mapped_column(Integer)


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("rating IS NULL OR (rating >= 0 AND rating <= 5)", name="rating_range"),
        CheckConstraint(
            "review_count IS NULL OR review_count >= 0", name="review_count_non_negative"
        ),
    )

    product_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    sku: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(Text)
    brand_id: Mapped[str] = mapped_column(ForeignKey("brands.brand_id"), index=True)
    # Resolved at ingest by matching (category_name, subcategory_name) against categories.
    subcategory_id: Mapped[str | None] = mapped_column(
        ForeignKey("categories.subcategory_id"), index=True
    )
    category_name: Mapped[str] = mapped_column(Text)
    subcategory_name: Mapped[str] = mapped_column(Text)
    short_description: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    recommended_for: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")
    not_recommended_for: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")
    key_features: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")
    color: Mapped[str | None] = mapped_column(Text)
    weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(8, 3))
    width_cm: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    height_cm: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    depth_cm: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    warranty_months: Mapped[int | None] = mapped_column(Integer)
    return_days: Mapped[int | None] = mapped_column(Integer)
    rating: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    review_count: Mapped[int | None] = mapped_column(Integer)
    launch_date: Mapped[date | None] = mapped_column(Date)
    active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    image_url: Mapped[str | None] = mapped_column(Text)


class ProductSpecification(Base):
    __tablename__ = "product_specifications"
    # The unique index starts with product_id, so it also serves lookups by product.
    __table_args__ = (UniqueConstraint("product_id", "attribute_group", "attribute_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[str] = mapped_column(
        ForeignKey("products.product_id", ondelete="CASCADE")
    )
    attribute_group: Mapped[str] = mapped_column(Text)
    attribute_name: Mapped[str] = mapped_column(Text)
    value_text: Mapped[str | None] = mapped_column(Text)
    value_number: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    unit: Mapped[str | None] = mapped_column(Text)


class ProductRelation(Base):
    __tablename__ = "product_relations"
    __table_args__ = (
        CheckConstraint("product_id <> related_product_id", name="not_self_related"),
        CheckConstraint("strength >= 0 AND strength <= 1", name="strength_range"),
    )

    product_id: Mapped[str] = mapped_column(
        ForeignKey("products.product_id", ondelete="CASCADE"), primary_key=True
    )
    related_product_id: Mapped[str] = mapped_column(
        ForeignKey("products.product_id", ondelete="CASCADE"), primary_key=True, index=True
    )
    relation_type: Mapped[str] = mapped_column(String(32), primary_key=True)
    strength: Mapped[Decimal] = mapped_column(Numeric(4, 3))


class ProductEmbedding(Base):
    """Vector of the static text of a product. Filled by the semantic search ingest."""

    __tablename__ = "product_embeddings"

    product_id: Mapped[str] = mapped_column(
        ForeignKey("products.product_id", ondelete="CASCADE"), primary_key=True
    )
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSIONS))
    model: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
