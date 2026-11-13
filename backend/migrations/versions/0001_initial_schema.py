"""Initial schema: catalog, price and stock, purchase and conversation tables.

Revision ID: 0001
Revises:
Create Date: 2026-11-13 00:15:47.820410
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = '0001'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # pgvector provides the vector column type used by product_embeddings.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table('brands',
    sa.Column('brand_id', sa.String(length=16), nullable=False),
    sa.Column('brand_name', sa.Text(), nullable=False),
    sa.Column('country_of_origin', sa.Text(), nullable=True),
    sa.Column('positioning', sa.Text(), nullable=True),
    sa.PrimaryKeyConstraint('brand_id', name=op.f('pk_brands'))
    )
    op.create_table('carts',
    sa.Column('cart_id', sa.Uuid(), nullable=False),
    sa.Column('session_id', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('cart_id', name=op.f('pk_carts')),
    sa.UniqueConstraint('session_id', name=op.f('uq_carts_session_id'))
    )
    op.create_table('categories',
    sa.Column('subcategory_id', sa.String(length=16), nullable=False),
    sa.Column('subcategory_name', sa.Text(), nullable=False),
    sa.Column('category_id', sa.String(length=16), nullable=False),
    sa.Column('category_name', sa.Text(), nullable=False),
    sa.Column('department', sa.Text(), nullable=True),
    sa.Column('sort_order', sa.Integer(), nullable=True),
    sa.PrimaryKeyConstraint('subcategory_id', name=op.f('pk_categories')),
    sa.UniqueConstraint('category_name', 'subcategory_name', name=op.f('uq_categories_category_name_subcategory_name'))
    )
    op.create_index(op.f('ix_categories_category_id'), 'categories', ['category_id'], unique=False)
    op.create_table('conversations',
    sa.Column('conversation_id', sa.Uuid(), nullable=False),
    sa.Column('session_id', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('conversation_id', name=op.f('pk_conversations'))
    )
    op.create_index(op.f('ix_conversations_session_id'), 'conversations', ['session_id'], unique=False)
    op.create_table('warehouses',
    sa.Column('warehouse_id', sa.String(length=16), nullable=False),
    sa.Column('warehouse_name', sa.Text(), nullable=False),
    sa.Column('city', sa.Text(), nullable=True),
    sa.Column('department', sa.Text(), nullable=True),
    sa.Column('country', sa.Text(), nullable=True),
    sa.Column('pickup_enabled', sa.Boolean(), server_default='true', nullable=False),
    sa.Column('shipping_enabled', sa.Boolean(), server_default='true', nullable=False),
    sa.PrimaryKeyConstraint('warehouse_id', name=op.f('pk_warehouses'))
    )
    op.create_table('messages',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('conversation_id', sa.Uuid(), nullable=False),
    sa.Column('role', sa.String(length=16), nullable=False),
    sa.Column('content', sa.Text(), server_default='', nullable=False),
    sa.Column('blocks', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('tool_calls', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("role IN ('user', 'assistant', 'tool')", name=op.f('ck_messages_role_valid')),
    sa.ForeignKeyConstraint(['conversation_id'], ['conversations.conversation_id'], name=op.f('fk_messages_conversation_id_conversations'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_messages'))
    )
    op.create_index('ix_messages_conversation_id_created_at', 'messages', ['conversation_id', 'created_at'], unique=False)
    op.create_table('orders',
    sa.Column('order_id', sa.String(length=32), nullable=False),
    sa.Column('session_id', sa.String(length=64), nullable=False),
    sa.Column('status', sa.String(length=32), server_default='pending_confirmation', nullable=False),
    sa.Column('customer_name', sa.Text(), nullable=False),
    sa.Column('customer_email', sa.Text(), nullable=False),
    sa.Column('customer_address', sa.Text(), nullable=False),
    sa.Column('delivery_method', sa.String(length=16), nullable=False),
    sa.Column('warehouse_id', sa.String(length=16), nullable=True),
    sa.Column('total', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('currency', sa.String(length=3), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("delivery_method <> 'pickup' OR warehouse_id IS NOT NULL", name=op.f('ck_orders_pickup_requires_warehouse')),
    sa.CheckConstraint("delivery_method IN ('pickup', 'shipping')", name=op.f('ck_orders_delivery_method_valid')),
    sa.CheckConstraint("status IN ('pending_confirmation', 'confirmed', 'cancelled')", name=op.f('ck_orders_status_valid')),
    sa.CheckConstraint('total >= 0', name=op.f('ck_orders_total_non_negative')),
    sa.ForeignKeyConstraint(['warehouse_id'], ['warehouses.warehouse_id'], name=op.f('fk_orders_warehouse_id_warehouses')),
    sa.PrimaryKeyConstraint('order_id', name=op.f('pk_orders'))
    )
    op.create_index(op.f('ix_orders_session_id'), 'orders', ['session_id'], unique=False)
    op.create_table('products',
    sa.Column('product_id', sa.String(length=32), nullable=False),
    sa.Column('sku', sa.String(length=32), nullable=False),
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('brand_id', sa.String(length=16), nullable=False),
    sa.Column('subcategory_id', sa.String(length=16), nullable=True),
    sa.Column('category_name', sa.Text(), nullable=False),
    sa.Column('subcategory_name', sa.Text(), nullable=False),
    sa.Column('short_description', sa.Text(), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('recommended_for', postgresql.ARRAY(sa.Text()), server_default='{}', nullable=False),
    sa.Column('not_recommended_for', postgresql.ARRAY(sa.Text()), server_default='{}', nullable=False),
    sa.Column('key_features', postgresql.ARRAY(sa.Text()), server_default='{}', nullable=False),
    sa.Column('tags', postgresql.ARRAY(sa.Text()), server_default='{}', nullable=False),
    sa.Column('color', sa.Text(), nullable=True),
    sa.Column('weight_kg', sa.Numeric(precision=8, scale=3), nullable=True),
    sa.Column('width_cm', sa.Numeric(precision=8, scale=2), nullable=True),
    sa.Column('height_cm', sa.Numeric(precision=8, scale=2), nullable=True),
    sa.Column('depth_cm', sa.Numeric(precision=8, scale=2), nullable=True),
    sa.Column('warranty_months', sa.Integer(), nullable=True),
    sa.Column('return_days', sa.Integer(), nullable=True),
    sa.Column('rating', sa.Numeric(precision=3, scale=2), nullable=True),
    sa.Column('review_count', sa.Integer(), nullable=True),
    sa.Column('launch_date', sa.Date(), nullable=True),
    sa.Column('active', sa.Boolean(), server_default='true', nullable=False),
    sa.Column('image_url', sa.Text(), nullable=True),
    sa.CheckConstraint('rating IS NULL OR (rating >= 0 AND rating <= 5)', name=op.f('ck_products_rating_range')),
    sa.CheckConstraint('review_count IS NULL OR review_count >= 0', name=op.f('ck_products_review_count_non_negative')),
    sa.ForeignKeyConstraint(['brand_id'], ['brands.brand_id'], name=op.f('fk_products_brand_id_brands')),
    sa.ForeignKeyConstraint(['subcategory_id'], ['categories.subcategory_id'], name=op.f('fk_products_subcategory_id_categories')),
    sa.PrimaryKeyConstraint('product_id', name=op.f('pk_products')),
    sa.UniqueConstraint('sku', name=op.f('uq_products_sku'))
    )
    op.create_index(op.f('ix_products_brand_id'), 'products', ['brand_id'], unique=False)
    op.create_index(op.f('ix_products_subcategory_id'), 'products', ['subcategory_id'], unique=False)
    op.create_table('cart_items',
    sa.Column('cart_id', sa.Uuid(), nullable=False),
    sa.Column('product_id', sa.String(length=32), nullable=False),
    sa.Column('quantity', sa.Integer(), nullable=False),
    sa.Column('added_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('quantity > 0', name=op.f('ck_cart_items_quantity_positive')),
    sa.ForeignKeyConstraint(['cart_id'], ['carts.cart_id'], name=op.f('fk_cart_items_cart_id_carts'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['product_id'], ['products.product_id'], name=op.f('fk_cart_items_product_id_products')),
    sa.PrimaryKeyConstraint('cart_id', 'product_id', name=op.f('pk_cart_items'))
    )
    op.create_index(op.f('ix_cart_items_product_id'), 'cart_items', ['product_id'], unique=False)
    op.create_table('inventory',
    sa.Column('product_id', sa.String(length=32), nullable=False),
    sa.Column('warehouse_id', sa.String(length=16), nullable=False),
    sa.Column('on_hand_qty', sa.Integer(), nullable=False),
    sa.Column('reserved_qty', sa.Integer(), server_default='0', nullable=False),
    sa.Column('available_qty', sa.Integer(), nullable=False),
    sa.Column('inventory_status', sa.Text(), nullable=True),
    sa.Column('inventory_updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint('available_qty >= 0', name=op.f('ck_inventory_available_qty_non_negative')),
    sa.CheckConstraint('on_hand_qty >= 0', name=op.f('ck_inventory_on_hand_qty_non_negative')),
    sa.CheckConstraint('reserved_qty >= 0', name=op.f('ck_inventory_reserved_qty_non_negative')),
    sa.ForeignKeyConstraint(['product_id'], ['products.product_id'], name=op.f('fk_inventory_product_id_products'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['warehouse_id'], ['warehouses.warehouse_id'], name=op.f('fk_inventory_warehouse_id_warehouses')),
    sa.PrimaryKeyConstraint('product_id', 'warehouse_id', name=op.f('pk_inventory'))
    )
    op.create_index(op.f('ix_inventory_warehouse_id'), 'inventory', ['warehouse_id'], unique=False)
    op.create_table('order_items',
    sa.Column('order_id', sa.String(length=32), nullable=False),
    sa.Column('product_id', sa.String(length=32), nullable=False),
    sa.Column('product_name', sa.Text(), nullable=False),
    sa.Column('unit_price', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('quantity', sa.Integer(), nullable=False),
    sa.Column('line_total', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.CheckConstraint('line_total >= 0', name=op.f('ck_order_items_line_total_non_negative')),
    sa.CheckConstraint('quantity > 0', name=op.f('ck_order_items_quantity_positive')),
    sa.CheckConstraint('unit_price >= 0', name=op.f('ck_order_items_unit_price_non_negative')),
    sa.ForeignKeyConstraint(['order_id'], ['orders.order_id'], name=op.f('fk_order_items_order_id_orders'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['product_id'], ['products.product_id'], name=op.f('fk_order_items_product_id_products')),
    sa.PrimaryKeyConstraint('order_id', 'product_id', name=op.f('pk_order_items'))
    )
    op.create_index(op.f('ix_order_items_product_id'), 'order_items', ['product_id'], unique=False)
    op.create_table('prices',
    sa.Column('product_id', sa.String(length=32), nullable=False),
    sa.Column('currency', sa.String(length=3), nullable=False),
    sa.Column('list_price', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('current_price', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('discount_percent', sa.Numeric(precision=5, scale=2), server_default='0', nullable=False),
    sa.Column('tax_included', sa.Boolean(), server_default='true', nullable=False),
    sa.Column('price_updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint('current_price >= 0', name=op.f('ck_prices_current_price_non_negative')),
    sa.CheckConstraint('discount_percent >= 0 AND discount_percent <= 100', name=op.f('ck_prices_discount_percent_range')),
    sa.CheckConstraint('list_price >= 0', name=op.f('ck_prices_list_price_non_negative')),
    sa.ForeignKeyConstraint(['product_id'], ['products.product_id'], name=op.f('fk_prices_product_id_products'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('product_id', name=op.f('pk_prices'))
    )
    op.create_table('product_embeddings',
    sa.Column('product_id', sa.String(length=32), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('embedding', Vector(768), nullable=False),
    sa.Column('model', sa.Text(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['product_id'], ['products.product_id'], name=op.f('fk_product_embeddings_product_id_products'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('product_id', name=op.f('pk_product_embeddings'))
    )
    op.create_table('product_relations',
    sa.Column('product_id', sa.String(length=32), nullable=False),
    sa.Column('related_product_id', sa.String(length=32), nullable=False),
    sa.Column('relation_type', sa.String(length=32), nullable=False),
    sa.Column('strength', sa.Numeric(precision=4, scale=3), nullable=False),
    sa.CheckConstraint('product_id <> related_product_id', name=op.f('ck_product_relations_not_self_related')),
    sa.CheckConstraint('strength >= 0 AND strength <= 1', name=op.f('ck_product_relations_strength_range')),
    sa.ForeignKeyConstraint(['product_id'], ['products.product_id'], name=op.f('fk_product_relations_product_id_products'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['related_product_id'], ['products.product_id'], name=op.f('fk_product_relations_related_product_id_products'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('product_id', 'related_product_id', 'relation_type', name=op.f('pk_product_relations'))
    )
    op.create_index(op.f('ix_product_relations_related_product_id'), 'product_relations', ['related_product_id'], unique=False)
    op.create_table('product_specifications',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('product_id', sa.String(length=32), nullable=False),
    sa.Column('attribute_group', sa.Text(), nullable=False),
    sa.Column('attribute_name', sa.Text(), nullable=False),
    sa.Column('value_text', sa.Text(), nullable=True),
    sa.Column('value_number', sa.Numeric(precision=14, scale=4), nullable=True),
    sa.Column('unit', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['product_id'], ['products.product_id'], name=op.f('fk_product_specifications_product_id_products'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_product_specifications')),
    sa.UniqueConstraint('product_id', 'attribute_group', 'attribute_name', name=op.f('uq_product_specifications_product_id_attribute_group_attribute_name'))
    )
    op.create_table('order_allocations',
    sa.Column('order_id', sa.String(length=32), nullable=False),
    sa.Column('product_id', sa.String(length=32), nullable=False),
    sa.Column('warehouse_id', sa.String(length=16), nullable=False),
    sa.Column('quantity', sa.Integer(), nullable=False),
    sa.CheckConstraint('quantity > 0', name=op.f('ck_order_allocations_quantity_positive')),
    sa.ForeignKeyConstraint(['order_id', 'product_id'], ['order_items.order_id', 'order_items.product_id'], name=op.f('fk_order_allocations_order_id_product_id_order_items'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['warehouse_id'], ['warehouses.warehouse_id'], name=op.f('fk_order_allocations_warehouse_id_warehouses')),
    sa.PrimaryKeyConstraint('order_id', 'product_id', 'warehouse_id', name=op.f('pk_order_allocations'))
    )


def downgrade() -> None:
    op.drop_table('order_allocations')
    op.drop_table('product_specifications')
    op.drop_index(op.f('ix_product_relations_related_product_id'), table_name='product_relations')
    op.drop_table('product_relations')
    op.drop_table('product_embeddings')
    op.drop_table('prices')
    op.drop_index(op.f('ix_order_items_product_id'), table_name='order_items')
    op.drop_table('order_items')
    op.drop_index(op.f('ix_inventory_warehouse_id'), table_name='inventory')
    op.drop_table('inventory')
    op.drop_index(op.f('ix_cart_items_product_id'), table_name='cart_items')
    op.drop_table('cart_items')
    op.drop_index(op.f('ix_products_subcategory_id'), table_name='products')
    op.drop_index(op.f('ix_products_brand_id'), table_name='products')
    op.drop_table('products')
    op.drop_index(op.f('ix_orders_session_id'), table_name='orders')
    op.drop_table('orders')
    op.drop_index('ix_messages_conversation_id_created_at', table_name='messages')
    op.drop_table('messages')
    op.drop_table('warehouses')
    op.drop_index(op.f('ix_conversations_session_id'), table_name='conversations')
    op.drop_table('conversations')
    op.drop_index(op.f('ix_categories_category_id'), table_name='categories')
    op.drop_table('categories')
    op.drop_table('carts')
    op.drop_table('brands')
    op.execute("DROP EXTENSION IF EXISTS vector")
