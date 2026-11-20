"""What the agent loop may write to the logs about the arguments of a tool call.

The model writes the arguments from what the customer said, so free text can carry personal
data. Only numbers, flags and product ids are logged as they are; any other text is replaced by
its length, which is enough to follow a turn without keeping what was typed.
"""

import re
from typing import Any

_PRODUCT_ID = re.compile(r"^MN-[A-Z0-9]+(-[A-Z0-9]+)*$")


def _scalar(value: Any) -> Any:
    if isinstance(value, bool | int | float) or value is None:
        return value
    if isinstance(value, str):
        return value if _PRODUCT_ID.match(value) else f"<text {len(value)} chars>"
    return "<object>"


def loggable_arguments(arguments: dict[str, Any]) -> dict[str, Any]:
    return {
        key: [_scalar(item) for item in value] if isinstance(value, list) else _scalar(value)
        for key, value in arguments.items()
    }
