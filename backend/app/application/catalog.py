"""Catalog use cases."""

from app.application.ports import CatalogRepository
from app.domain.catalog import (
    MAX_COMPARED_PRODUCTS,
    MIN_COMPARED_PRODUCTS,
    CategoryGroup,
    Comparison,
    ComparisonAttribute,
    InvalidComparison,
    ProductDetail,
    ProductFilters,
    ProductNotFound,
    ProductPage,
    SortOrder,
    Warehouse,
)

MAX_PAGE_SIZE = 100


def list_products(
    repository: CatalogRepository,
    filters: ProductFilters,
    sort: SortOrder | None = None,
    page: int = 1,
    page_size: int = 20,
) -> ProductPage:
    return repository.list_products(filters, sort, page, min(page_size, MAX_PAGE_SIZE))


def get_product(repository: CatalogRepository, product_id: str) -> ProductDetail:
    detail = repository.get_detail(product_id)
    if detail is None:
        raise ProductNotFound(product_id)
    return detail


def compare_products(repository: CatalogRepository, product_ids: list[str]) -> Comparison:
    ids = list(dict.fromkeys(product_ids))  # drop repeated ids, keep the requested order
    if not MIN_COMPARED_PRODUCTS <= len(ids) <= MAX_COMPARED_PRODUCTS:
        raise InvalidComparison(
            f"Between {MIN_COMPARED_PRODUCTS} and {MAX_COMPARED_PRODUCTS} "
            "different products are needed"
        )
    by_id = {summary.product_id: summary for summary in repository.get_summaries(ids)}
    for product_id in ids:
        if product_id not in by_id:
            raise ProductNotFound(product_id)

    specifications = repository.get_specifications(ids)
    rows: dict[tuple[str, str], ComparisonAttribute] = {}
    for product_id in ids:
        for spec in specifications.get(product_id, []):
            row = rows.setdefault(
                (spec.group, spec.name),
                ComparisonAttribute(spec.group, spec.name, spec.unit, dict.fromkeys(ids)),
            )
            row.values[product_id] = spec.value
    return Comparison(products=[by_id[i] for i in ids], attributes=list(rows.values()))


def list_categories(repository: CatalogRepository) -> list[CategoryGroup]:
    return repository.list_categories()


def list_warehouses(repository: CatalogRepository) -> list[Warehouse]:
    return repository.list_warehouses()
