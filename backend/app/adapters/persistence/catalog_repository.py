"""SQLAlchemy implementation of the CatalogRepository port.

Price and stock are joined in every query, so each call reads the current database state.
"""

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.adapters.persistence.orm.catalog import (
    Brand,
    Category,
    Product,
    ProductRelation,
    ProductSpecification,
)
from app.adapters.persistence.orm.stock import Inventory, Price
from app.adapters.persistence.orm.stock import Warehouse as WarehouseRow
from app.domain.catalog import (
    Availability,
    CategoryGroup,
    ProductDetail,
    ProductFilters,
    ProductPage,
    ProductSummary,
    RelatedProduct,
    SortOrder,
    Specification,
    Warehouse,
)
from app.domain.catalog import (
    Price as PriceValue,
)

_stock = (
    select(Inventory.product_id, func.sum(Inventory.available_qty).label("qty"))
    .group_by(Inventory.product_id)
    .subquery("stock")
)
_available_qty = func.coalesce(_stock.c.qty, 0)


def _join_price_and_stock(stmt: Select) -> Select:
    return (
        stmt.join(Brand, Brand.brand_id == Product.brand_id)
        .outerjoin(Price, Price.product_id == Product.product_id)
        .outerjoin(_stock, _stock.c.product_id == Product.product_id)
    )


def _summary_query() -> Select:
    return _join_price_and_stock(
        select(Product, Brand.brand_name, Price, _available_qty.label("available_qty"))
    )


def _escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _conditions(filters: ProductFilters) -> list:
    conditions = []
    if filters.q:
        pattern = f"%{_escape_like(filters.q)}%"
        conditions.append(
            Product.name.ilike(pattern, escape="\\")
            | Brand.brand_name.ilike(pattern, escape="\\")
            | Product.short_description.ilike(pattern, escape="\\")
        )
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


def _order_by(sort: SortOrder | None) -> list:
    if sort == "price_asc":
        primary = [Price.current_price.asc().nulls_last()]
    elif sort == "price_desc":
        primary = [Price.current_price.desc().nulls_last()]
    elif sort == "rating":
        primary = [Product.rating.desc().nulls_last()]
    else:
        primary = []
    return [*primary, Product.product_id]


def _to_summary(row) -> ProductSummary:
    product, brand_name, price, available_qty = row
    return ProductSummary(
        product_id=product.product_id,
        sku=product.sku,
        name=product.name,
        brand=brand_name,
        category=product.category_name,
        subcategory=product.subcategory_name,
        short_description=product.short_description,
        image_url=product.image_url,
        rating=product.rating,
        review_count=product.review_count,
        price=None
        if price is None
        else PriceValue(
            current=price.current_price,
            list=price.list_price,
            discount_percent=price.discount_percent,
            currency=price.currency,
        ),
        available_qty=int(available_qty),
    )


def _to_specification(row: ProductSpecification) -> Specification:
    return Specification(
        group=row.attribute_group,
        name=row.attribute_name,
        value_text=row.value_text,
        value_number=row.value_number,
        unit=row.unit,
    )


class SqlAlchemyCatalogRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_products(
        self, filters: ProductFilters, sort: SortOrder | None, page: int, page_size: int
    ) -> ProductPage:
        conditions = [Product.active.is_(True), *_conditions(filters)]
        total = self._session.scalar(
            _join_price_and_stock(select(func.count(Product.product_id))).where(*conditions)
        )
        rows = self._session.execute(
            _summary_query()
            .where(*conditions)
            .order_by(*_order_by(sort))
            .limit(page_size)
            .offset((page - 1) * page_size)
        ).all()
        return ProductPage([_to_summary(r) for r in rows], page, page_size, total or 0)

    def get_summaries(self, product_ids: list[str]) -> list[ProductSummary]:
        rows = self._session.execute(
            _summary_query().where(Product.product_id.in_(product_ids))
        ).all()
        return [_to_summary(r) for r in rows]

    def get_detail(self, product_id: str) -> ProductDetail | None:
        row = self._session.execute(
            _summary_query().where(Product.product_id == product_id)
        ).first()
        if row is None:
            return None
        product = row[0]
        availability = self._session.execute(
            select(Inventory.available_qty, WarehouseRow)
            .join(WarehouseRow, WarehouseRow.warehouse_id == Inventory.warehouse_id)
            .where(Inventory.product_id == product_id)
            .order_by(WarehouseRow.warehouse_id)
        ).all()
        related = self._session.execute(
            select(ProductRelation, Product.name)
            .join(Product, Product.product_id == ProductRelation.related_product_id)
            .where(ProductRelation.product_id == product_id)
            .order_by(ProductRelation.strength.desc(), ProductRelation.related_product_id)
        ).all()
        return ProductDetail(
            summary=_to_summary(row),
            description=product.description,
            recommended_for=list(product.recommended_for or []),
            not_recommended_for=list(product.not_recommended_for or []),
            key_features=list(product.key_features or []),
            tags=list(product.tags or []),
            color=product.color,
            width_cm=product.width_cm,
            height_cm=product.height_cm,
            depth_cm=product.depth_cm,
            weight_kg=product.weight_kg,
            warranty_months=product.warranty_months,
            return_days=product.return_days,
            specifications=self.get_specifications([product_id]).get(product_id, []),
            availability=[
                Availability(w.warehouse_id, w.warehouse_name, w.city, qty, w.pickup_enabled)
                for qty, w in availability
            ],
            related=[
                RelatedProduct(r.related_product_id, name, r.relation_type, r.strength)
                for r, name in related
            ],
        )

    def get_specifications(self, product_ids: list[str]) -> dict[str, list[Specification]]:
        rows = self._session.scalars(
            select(ProductSpecification)
            .where(ProductSpecification.product_id.in_(product_ids))
            .order_by(ProductSpecification.id)
        )
        result: dict[str, list[Specification]] = {}
        for row in rows:
            result.setdefault(row.product_id, []).append(_to_specification(row))
        return result

    def list_categories(self) -> list[CategoryGroup]:
        rows = self._session.execute(
            select(Category.category_name, Category.subcategory_name).order_by(
                Category.category_id,
                Category.sort_order.asc().nulls_last(),
                Category.subcategory_name,
            )
        ).all()
        groups: dict[str, list[str]] = {}
        for category, subcategory in rows:
            groups.setdefault(category, []).append(subcategory)
        return [CategoryGroup(category, subs) for category, subs in groups.items()]

    def list_warehouses(self) -> list[Warehouse]:
        rows = self._session.scalars(select(WarehouseRow).order_by(WarehouseRow.warehouse_id))
        return [
            Warehouse(
                w.warehouse_id,
                w.warehouse_name,
                w.city,
                w.department,
                w.country,
                w.pickup_enabled,
                w.shipping_enabled,
            )
            for w in rows
        ]
