"""Catalog endpoints: products, comparison, categories and warehouses."""

from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.adapters.persistence.catalog_repository import SqlAlchemyCatalogRepository
from app.adapters.persistence.session import get_session
from app.application import catalog as use_cases
from app.application.ports import CatalogRepository
from app.domain.catalog import ProductDetail, ProductFilters, ProductSummary, SortOrder

router = APIRouter(prefix="/api", tags=["catalog"])


class PriceResponse(BaseModel):
    current: float
    list: float
    discount_percent: float
    currency: str


class ProductSummaryResponse(BaseModel):
    product_id: str
    sku: str
    name: str
    brand: str
    category: str
    subcategory: str
    short_description: str | None
    image_url: str | None
    rating: float | None
    review_count: int | None
    price: PriceResponse | None
    available_qty: int
    in_stock: bool


class ProductPageResponse(BaseModel):
    items: list[ProductSummaryResponse]
    page: int
    page_size: int
    total: int


class DimensionsResponse(BaseModel):
    width: float | None
    height: float | None
    depth: float | None


class SpecificationResponse(BaseModel):
    group: str
    name: str
    value: str | None
    unit: str | None


class AvailabilityResponse(BaseModel):
    warehouse_id: str
    warehouse_name: str
    city: str | None
    available_qty: int
    pickup_enabled: bool


class RelatedProductResponse(BaseModel):
    product_id: str
    name: str
    relation_type: str
    strength: float


class ProductDetailResponse(ProductSummaryResponse):
    description: str | None
    recommended_for: list[str]
    not_recommended_for: list[str]
    key_features: list[str]
    tags: list[str]
    color: str | None
    dimensions_cm: DimensionsResponse
    weight_kg: float | None
    warranty_months: int | None
    return_days: int | None
    specifications: list[SpecificationResponse]
    availability: list[AvailabilityResponse]
    related: list[RelatedProductResponse]


class ComparisonAttributeResponse(BaseModel):
    group: str
    name: str
    unit: str | None
    values: dict[str, str | None]


class ComparisonResponse(BaseModel):
    products: list[ProductSummaryResponse]
    attributes: list[ComparisonAttributeResponse]


class CategoryResponse(BaseModel):
    category: str
    subcategories: list[str]


class WarehouseResponse(BaseModel):
    warehouse_id: str
    warehouse_name: str
    city: str | None
    department: str | None
    country: str | None
    pickup_enabled: bool
    shipping_enabled: bool


def get_catalog_repository(session: Session = Depends(get_session)) -> CatalogRepository:
    return SqlAlchemyCatalogRepository(session)


def _number(value: Decimal | None) -> float | None:
    return None if value is None else float(value)


def _summary(product: ProductSummary) -> ProductSummaryResponse:
    price = product.price
    return ProductSummaryResponse(
        product_id=product.product_id,
        sku=product.sku,
        name=product.name,
        brand=product.brand,
        category=product.category,
        subcategory=product.subcategory,
        short_description=product.short_description,
        image_url=product.image_url,
        rating=_number(product.rating),
        review_count=product.review_count,
        price=None
        if price is None
        else PriceResponse(
            current=float(price.current),
            list=float(price.list),
            discount_percent=float(price.discount_percent),
            currency=price.currency,
        ),
        available_qty=product.available_qty,
        in_stock=product.in_stock,
    )


def _detail(detail: ProductDetail) -> ProductDetailResponse:
    return ProductDetailResponse(
        **_summary(detail.summary).model_dump(),
        description=detail.description,
        recommended_for=detail.recommended_for,
        not_recommended_for=detail.not_recommended_for,
        key_features=detail.key_features,
        tags=detail.tags,
        color=detail.color,
        dimensions_cm=DimensionsResponse(
            width=_number(detail.width_cm),
            height=_number(detail.height_cm),
            depth=_number(detail.depth_cm),
        ),
        weight_kg=_number(detail.weight_kg),
        warranty_months=detail.warranty_months,
        return_days=detail.return_days,
        specifications=[
            SpecificationResponse(group=s.group, name=s.name, value=s.value, unit=s.unit)
            for s in detail.specifications
        ],
        availability=[AvailabilityResponse(**vars(a)) for a in detail.availability],
        related=[
            RelatedProductResponse(
                product_id=r.product_id,
                name=r.name,
                relation_type=r.relation_type,
                strength=float(r.strength),
            )
            for r in detail.related
        ],
    )


@router.get("/products", response_model=ProductPageResponse)
def list_products(
    q: str | None = None,
    category: str | None = None,
    subcategory: str | None = None,
    brand: str | None = None,
    min_price: Decimal | None = Query(None, ge=0),
    max_price: Decimal | None = Query(None, ge=0),
    in_stock: bool | None = None,
    sort: SortOrder | None = None,
    page: int = Query(1, ge=1, le=10000),
    page_size: int = Query(20, ge=1),  # values above 100 are capped by the use case
    repository: CatalogRepository = Depends(get_catalog_repository),
) -> ProductPageResponse:
    filters = ProductFilters(q, category, subcategory, brand, min_price, max_price, in_stock)
    result = use_cases.list_products(repository, filters, sort, page, page_size)
    return ProductPageResponse(
        items=[_summary(p) for p in result.items],
        page=result.page,
        page_size=result.page_size,
        total=result.total,
    )


# Declared before /products/{product_id} so "compare" is not read as a product id.
@router.get("/products/compare", response_model=ComparisonResponse)
def compare_products(
    ids: str,
    repository: CatalogRepository = Depends(get_catalog_repository),
) -> ComparisonResponse:
    product_ids = [i.strip() for i in ids.split(",") if i.strip()]
    result = use_cases.compare_products(repository, product_ids)
    return ComparisonResponse(
        products=[_summary(p) for p in result.products],
        attributes=[ComparisonAttributeResponse(**vars(a)) for a in result.attributes],
    )


@router.get("/products/{product_id}", response_model=ProductDetailResponse)
def get_product(
    product_id: str,
    repository: CatalogRepository = Depends(get_catalog_repository),
) -> ProductDetailResponse:
    return _detail(use_cases.get_product(repository, product_id))


@router.get("/categories", response_model=list[CategoryResponse])
def list_categories(
    repository: CatalogRepository = Depends(get_catalog_repository),
) -> list[CategoryResponse]:
    return [CategoryResponse(**vars(c)) for c in use_cases.list_categories(repository)]


@router.get("/warehouses", response_model=list[WarehouseResponse])
def list_warehouses(
    repository: CatalogRepository = Depends(get_catalog_repository),
) -> list[WarehouseResponse]:
    return [WarehouseResponse(**vars(w)) for w in use_cases.list_warehouses(repository)]
