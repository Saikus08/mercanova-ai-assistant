"""ORM models. Importing this package registers every table on ``Base.metadata``."""

from app.adapters.persistence.base import Base
from app.adapters.persistence.orm.catalog import (
    EMBEDDING_DIMENSIONS,
    Brand,
    Category,
    Product,
    ProductEmbedding,
    ProductRelation,
    ProductSpecification,
)
from app.adapters.persistence.orm.conversation import Conversation, Message
from app.adapters.persistence.orm.purchase import (
    Cart,
    CartItem,
    Order,
    OrderAllocation,
    OrderItem,
)
from app.adapters.persistence.orm.stock import Inventory, Price, Warehouse

__all__ = [
    "EMBEDDING_DIMENSIONS",
    "Base",
    "Brand",
    "Cart",
    "CartItem",
    "Category",
    "Conversation",
    "Inventory",
    "Message",
    "Order",
    "OrderAllocation",
    "OrderItem",
    "Price",
    "Product",
    "ProductEmbedding",
    "ProductRelation",
    "ProductSpecification",
    "Warehouse",
]
