"""Pure helpers that check what the assistant says against what tools returned this turn."""

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

from app.domain.agent import ShownProduct

PRICE_FILTERS = ("min_price", "max_price")
SEARCH_FILTERS = ("category", "subcategory", "brand", "min_price", "max_price")
VAGUE_MAX_WORDS = 3
_CENTS = Decimal("0.01")
_MAX_AMOUNT = Decimal("1e12")  # far above any price; bigger numbers are codes or noise
_NUMBER = r"\d+(?:[.,]\d+)*"
_NUMBER_RE = re.compile(_NUMBER)
_AMOUNT_RE = re.compile(
    rf"(?:USD|US\$|U\$S|\$)\s*(?P<before>{_NUMBER})"
    rf"|(?P<after>{_NUMBER})\s*(?:USD|dólares|dolares|dólar)\b",
    re.IGNORECASE,
)
_THOUSANDS_GROUP = 3


def _parse_number(token: str) -> Decimal | None:
    """Read '1.299,50', '1,299.50', '1299.5' or '1.299' as a Decimal."""
    has_dot, has_comma = "." in token, "," in token
    if has_dot and has_comma:
        decimal_mark = "." if token.rfind(".") > token.rfind(",") else ","
    elif has_dot or has_comma:
        mark = "." if has_dot else ","
        head, *groups = token.split(mark)
        looks_like_thousands = len(groups) > 1 or (
            len(groups[0]) == _THOUSANDS_GROUP and head != "0"
        )
        decimal_mark = None if looks_like_thousands else mark
    else:
        decimal_mark = None
    if decimal_mark is None:
        normalized = token.replace(".", "").replace(",", "")
    else:
        thousands = "," if decimal_mark == "." else "."
        normalized = token.replace(thousands, "").replace(decimal_mark, ".")
    try:
        return Decimal(normalized)
    except InvalidOperation:
        return None


def _quantize(value: Decimal) -> Decimal | None:
    """Value rounded to cents, or None when it is not a finite, plausible amount.

    Decimal.quantize raises on numbers with too many digits and on infinity, and customer text
    or model arguments can hold both; such numbers are never a price we can vouch for.
    """
    if not value.is_finite() or abs(value) >= _MAX_AMOUNT:
        return None
    return value.quantize(_CENTS)


def _cents(values: Iterable[Decimal]) -> set[Decimal]:
    return {cents for value in values if (cents := _quantize(value)) is not None}


def numbers_in_text(text: str) -> set[Decimal]:
    parsed = (_parse_number(token) for token in _NUMBER_RE.findall(text))
    return {number for number in parsed if number is not None}


def numbers_in_payload(obj: Any) -> set[Decimal]:
    if isinstance(obj, bool):
        return set()
    if isinstance(obj, int | float):
        return {Decimal(str(obj))}
    found: set[Decimal] = set()
    if isinstance(obj, dict):
        for value in obj.values():
            found |= numbers_in_payload(value)
    elif isinstance(obj, list | tuple):
        for value in obj:
            found |= numbers_in_payload(value)
    return found


def amounts_in_reply(text: str) -> list[Decimal]:
    amounts = []
    for match in _AMOUNT_RE.finditer(text):
        amount = _parse_number(match.group("before") or match.group("after"))
        if amount is not None:
            amounts.append(amount)
    return amounts


def ungrounded_amounts(reply: str, allowed: set[Decimal]) -> list[Decimal]:
    known = _cents(allowed)
    return [amount for amount in amounts_in_reply(reply) if _quantize(amount) not in known]


def ungrounded_price_filters(arguments: dict[str, Any], user_texts: list[str]) -> list[str]:
    """Price filter arguments whose number the customer never wrote."""
    stated = _cents(number for text in user_texts for number in numbers_in_text(text))
    flagged = []
    for name in PRICE_FILTERS:
        value = arguments.get(name)
        if value is None or isinstance(value, bool):
            continue
        try:
            number = Decimal(str(value))
        except InvalidOperation:
            continue  # the dispatcher rejects the wrong type
        if _quantize(number) not in stated:
            flagged.append(name)
    return flagged


def unknown_product_ids(
    arguments: dict[str, Any], known_ids: set[str], user_texts: list[str]
) -> list[str]:
    """Product ids in the arguments that no tool returned and the customer did not write."""
    sent = [arguments.get("product_id"), *(arguments.get("product_ids") or [])]
    ids = [value for value in sent if isinstance(value, str) and value.strip()]
    return [i for i in ids if i.strip() not in known_ids and not any(i in t for t in user_texts)]


def too_vague_search(arguments: dict[str, Any], user_texts: list[str]) -> bool:
    """A search with only a query, after a customer said almost nothing and gave no number."""
    if "query" not in arguments:
        return False
    if any(arguments.get(name) is not None for name in SEARCH_FILTERS):
        return False
    joined = " ".join(user_texts)
    return len(joined.split()) <= VAGUE_MAX_WORDS and not any(c.isdigit() for c in joined)


def leaked_tool_names(text: str, names: Iterable[str]) -> list[str]:
    """Registered tool names written in the text (whole word, any case), in the given order."""
    return [
        name
        for name in names
        if re.search(rf"(?<![\w]){re.escape(name)}(?![\w])", text, re.IGNORECASE)
    ]


def _is_card(item: Any) -> bool:
    return isinstance(item, dict) and "product_id" in item and "name" in item


def shown_products(payload: dict[str, Any]) -> list[ShownProduct]:
    """Products a tool result put in front of the customer, in order."""
    products = []
    for key in ("products", "alternatives"):
        items = payload.get(key)
        if isinstance(items, list):
            products.extend(
                ShownProduct(str(item["product_id"]), str(item["name"]))
                for item in items
                if _is_card(item)
            )
    return products


@dataclass
class TurnFacts:
    """What the successful tool results of this turn contain: the only allowed source of facts."""

    product_cards: dict[str, dict[str, Any]] = field(default_factory=dict)
    numbers: set[Decimal] = field(default_factory=set)

    def record(self, payload: dict[str, Any]) -> None:
        self.numbers |= numbers_in_payload(payload)
        cards = [_card for key in ("products", "alternatives") for _card in _items(payload, key)]
        if _is_card(payload):
            cards.append(payload)
        for card in cards:
            self.product_cards[str(card["product_id"])] = card


def result_cards(payload: dict[str, Any], key: str = "products") -> list[dict[str, Any]]:
    """The product cards of a tool result under ``key``, exactly as the tool returned them."""
    return _items(payload, key)


def _items(payload: dict[str, Any], key: str) -> list[dict[str, Any]]:
    items = payload.get(key)
    return [item for item in items if _is_card(item)] if isinstance(items, list) else []
