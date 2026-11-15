"""Catalog use cases with a fake repository (no database)."""

from decimal import Decimal

import pytest

from app.application.catalog import compare_products, get_product, list_products
from app.domain.catalog import (
    InvalidComparison,
    ProductFilters,
    ProductNotFound,
    ProductPage,
    ProductSummary,
    Specification,
    format_number,
)


def summary(product_id: str) -> ProductSummary:
    return ProductSummary(
        product_id=product_id,
        sku=f"SKU-{product_id}",
        name=f"Product {product_id}",
        brand="Flux",
        category="Monitors",
        subcategory="Gaming",
        short_description=None,
        image_url=None,
        rating=None,
        review_count=None,
        price=None,
        available_qty=0,
    )


def spec(group: str, name: str, text: str | None = None, number: str | None = None, unit=None):
    return Specification(group, name, text, Decimal(number) if number else None, unit)


class FakeCatalogRepository:
    def __init__(self, products: list[str], specs: dict[str, list[Specification]] | None = None):
        self.products = products
        self.specs = specs or {}
        self.last_page_size: int | None = None

    def list_products(self, filters, sort, page, page_size) -> ProductPage:
        self.last_page_size = page_size
        return ProductPage([], page, page_size, 0)

    def get_summaries(self, product_ids):
        # Returned in reverse on purpose: the use case must restore the requested order.
        return [summary(i) for i in reversed(product_ids) if i in self.products]

    def get_detail(self, product_id):
        return None

    def get_specifications(self, product_ids):
        return {i: self.specs[i] for i in product_ids if i in self.specs}


def test_format_number_drops_trailing_zeros() -> None:
    assert format_number(Decimal("24.0000")) == "24"
    assert format_number(Decimal("6.7400")) == "6.74"
    assert format_number(Decimal("1200")) == "1200"
    assert format_number(Decimal("0.5000")) == "0.5"


def test_specification_value_prefers_text_over_number() -> None:
    assert spec("G", "n", text="IPS", number="3").value == "IPS"
    assert spec("G", "n", number="24.0000").value == "24"
    assert spec("G", "n").value is None


def test_list_products_caps_page_size_at_100() -> None:
    repository = FakeCatalogRepository([])

    list_products(repository, ProductFilters(), page_size=500)

    assert repository.last_page_size == 100


def test_get_product_raises_not_found_when_repository_returns_none() -> None:
    with pytest.raises(ProductNotFound) as error:
        get_product(FakeCatalogRepository([]), "MN-X")

    assert error.value.product_id == "MN-X"


@pytest.mark.parametrize("ids", [[], ["A"], ["A", "A"], ["A", "B", "C", "D", "E"]])
def test_compare_rejects_invalid_number_of_products(ids: list[str]) -> None:
    with pytest.raises(InvalidComparison):
        compare_products(FakeCatalogRepository(["A", "B", "C", "D", "E"]), ids)


def test_compare_raises_not_found_for_unknown_id() -> None:
    with pytest.raises(ProductNotFound) as error:
        compare_products(FakeCatalogRepository(["A"]), ["A", "Z"])

    assert error.value.product_id == "Z"


def test_compare_keeps_requested_order_and_unions_attributes_with_null() -> None:
    repository = FakeCatalogRepository(
        ["A", "B"],
        {
            "A": [spec("Display", "Size", number="24.0000", unit="in"), spec("Display", "Panel", "IPS")],
            "B": [spec("Display", "Size", number="27.5000", unit="in"), spec("Power", "Watts", number="30")],
        },
    )

    comparison = compare_products(repository, ["B", "A"])

    assert [p.product_id for p in comparison.products] == ["B", "A"]
    by_name = {a.name: a for a in comparison.attributes}
    assert set(by_name) == {"Size", "Panel", "Watts"}
    assert by_name["Size"].values == {"B": "27.5", "A": "24"}
    assert by_name["Size"].unit == "in"
    assert by_name["Panel"].values == {"B": None, "A": "IPS"}
    assert by_name["Watts"].values == {"B": "30", "A": None}
