"""Tool definition shared by the registry, the dispatcher and the LLM adapter."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Any

from pydantic import AfterValidator, BaseModel

PRODUCT_ID_HINT = (
    "Product id exactly as returned by search_products in the product_id field, "
    "e.g. MN-DOC-0001. It is not the product name."
)


def _check_product_id(value: str) -> str:
    # A catalog id never contains whitespace; a product name usually does. The value is not
    # echoed back because it comes from the model.
    if not value or any(ch.isspace() for ch in value):
        raise ValueError(
            "product id must be an id returned by search_products (e.g. MN-DOC-0001), "
            "not a product name; call search_products with the product name first"
        )
    return value


ProductId = Annotated[str, AfterValidator(_check_product_id)]


class ToolDataUnavailable(ValueError):
    """The requested data does not exist for a valid product (e.g. it has no price row)."""


@dataclass(frozen=True)
class ToolContext:
    """Values injected by the harness. The model never sees or sets them."""

    session_id: str


@dataclass(frozen=True)
class ToolSpec:
    """What the LLM is told about a tool. The provider wire format is built by the adapter."""

    name: str
    description: str
    parameters: dict[str, Any]


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    args_model: type[BaseModel]  # must forbid extra fields
    handler: Callable[[Any, ToolContext], dict[str, Any]]

    def parameters_schema(self) -> dict[str, Any]:
        return self.args_model.model_json_schema()

    def spec(self) -> ToolSpec:
        return ToolSpec(self.name, self.description, self.parameters_schema())
