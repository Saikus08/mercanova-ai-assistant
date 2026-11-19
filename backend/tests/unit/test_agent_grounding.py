"""Pure grounding helpers: number parsing, reply amounts, price filter guard and turn facts."""

from decimal import Decimal

import pytest

from app.application.agent.grounding import (
    TurnFacts,
    amounts_in_reply,
    asks_for_negative_quantity,
    leaked_tool_names,
    numbers_in_payload,
    numbers_in_text,
    shown_products,
    too_vague_search,
    ungrounded_amounts,
    ungrounded_price_filters,
    unknown_product_ids,
)
from app.domain.agent import ShownProduct

D = Decimal


# --- numbers_in_text -----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1.299,50", {D("1299.50")}),
        ("1,299.50", {D("1299.50")}),
        ("1299.5", {D("1299.5")}),
        ("200", {D("200")}),
        ("1.299", {D("1299")}),
        ("1,299", {D("1299")}),
        ("12.345.678", {D("12345678")}),
        ("199,99", {D("199.99")}),
        ("no gastar más de USD 200.", {D("200")}),
        ("entre 100 y 250,5 dólares", {D("100"), D("250.5")}),
        ("sin números", set()),
    ],
)
def test_numbers_in_text_normalizes_separators(text, expected):
    assert numbers_in_text(text) == expected


# --- numbers_in_payload --------------------------------------------------------------------


def test_numbers_in_payload_finds_ints_and_floats_at_any_depth():
    payload = {"a": 1, "b": [{"c": 2.5}, {"d": {"e": 100}}], "f": "text 77"}

    assert numbers_in_payload(payload) == {D("1"), D("2.5"), D("100")}


def test_numbers_in_payload_excludes_booleans_and_strings():
    assert numbers_in_payload({"in_stock": True, "off": False, "id": "MN-001"}) == set()


# --- amounts_in_reply ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Cuesta USD 199,99", [D("199.99")]),
        ("Cuesta US$ 1.299,50 hoy", [D("1299.50")]),
        ("Sale U$S 85", [D("85")]),
        ("Sale $ 85", [D("85")]),
        ("Sale $85.", [D("85")]),
        ("Sale 150 USD", [D("150")]),
        ("Sale 150 dólares", [D("150")]),
        ("Sale 150 dolares", [D("150")]),
        ("Sale 1 dólar", [D("1")]),
        ("USD 10 y USD 20", [D("10"), D("20")]),
    ],
)
def test_amounts_in_reply_reads_money_with_markers(text, expected):
    assert amounts_in_reply(text) == expected


def test_amounts_in_reply_ignores_numbers_without_money_markers():
    assert amounts_in_reply("Tiene 40 horas de batería y 3 años de garantía") == []


# --- ungrounded_amounts --------------------------------------------------------------------


def test_ungrounded_amounts_returns_only_amounts_not_allowed():
    result = ungrounded_amounts("USD 199.99 y USD 300", {D("199.99")})

    assert result == [D("300")]


def test_ungrounded_amounts_compares_with_two_decimals():
    assert ungrounded_amounts("USD 200", {D("200.0")}) == []
    assert ungrounded_amounts("USD 199,99", {D("199.990")}) == []


def test_ungrounded_amounts_is_empty_without_amounts():
    assert ungrounded_amounts("Hola, ¿en qué te ayudo?", set()) == []


# --- ungrounded_price_filters --------------------------------------------------------------


def test_price_filter_stated_by_customer_is_grounded():
    assert ungrounded_price_filters({"max_price": 200.0}, ["no más de USD 200"]) == []


def test_price_filter_not_stated_by_customer_is_flagged():
    flagged = ungrounded_price_filters(
        {"query": "monitor", "max_price": 500}, ["Quiero un monitor"]
    )

    assert flagged == ["max_price"]


def test_price_filters_flag_each_invented_bound():
    arguments = {"min_price": 50, "max_price": 200}

    assert ungrounded_price_filters(arguments, ["hasta 200"]) == ["min_price"]


def test_price_filter_grounded_by_an_earlier_customer_message():
    assert ungrounded_price_filters({"max_price": 150}, ["mi presupuesto es 150", "hola"]) == []


def test_price_filter_accepts_thousand_separators_in_customer_text():
    assert ungrounded_price_filters({"max_price": 1500}, ["tengo 1.500 dólares"]) == []


def test_no_price_filters_means_nothing_flagged():
    assert ungrounded_price_filters({"query": "x", "max_price": None}, []) == []


# --- TurnFacts and shown_products ----------------------------------------------------------


def card(product_id, name="Product", price=100.0):
    return {"product_id": product_id, "name": name, "price": {"current": price}}


def test_facts_collect_cards_from_products_and_numbers():
    facts = TurnFacts()

    facts.record({"products": [card("MN-1", price=89.9), card("MN-2", price=120)], "count": 2})

    assert set(facts.product_cards) == {"MN-1", "MN-2"}
    assert facts.product_cards["MN-1"]["price"]["current"] == 89.9
    assert {D("89.9"), D("120"), D("2")} <= facts.numbers


def test_facts_collect_cards_from_alternatives():
    facts = TurnFacts()

    facts.record({"product_id": "MN-9", "alternatives": [card("MN-3")], "count": 1})

    assert set(facts.product_cards) == {"MN-3"}


def test_facts_collect_top_level_product_of_detail_price_and_stock_payloads():
    facts = TurnFacts()

    facts.record({"product_id": "MN-4", "name": "Webcam", "price": {"current": 49.5}})

    assert facts.product_cards["MN-4"]["name"] == "Webcam"
    assert D("49.5") in facts.numbers


def test_facts_ignore_payloads_without_product_name_or_id():
    facts = TurnFacts()

    facts.record({"items": [{"product_id": "MN-5", "name": "Cart line"}], "total": 10})

    assert facts.product_cards == {}
    assert D("10") in facts.numbers


def test_facts_keep_the_latest_card_of_a_product():
    facts = TurnFacts()

    facts.record({"products": [card("MN-1", price=100)]})
    facts.record({"products": [card("MN-1", price=90)]})

    assert facts.product_cards["MN-1"]["price"]["current"] == 90


def test_shown_products_reads_products_in_order():
    payload = {"products": [card("MN-1", "A"), card("MN-2", "B")]}

    assert shown_products(payload) == [ShownProduct("MN-1", "A"), ShownProduct("MN-2", "B")]


def test_shown_products_reads_alternatives():
    payload = {"product_id": "MN-9", "alternatives": [card("MN-3", "C")]}

    assert shown_products(payload) == [ShownProduct("MN-3", "C")]


def test_shown_products_is_empty_for_other_payloads():
    assert shown_products({"product_id": "MN-1", "name": "A", "price": {}}) == []
    assert shown_products({"error": "x", "hint": "y"}) == []


# --- too_vague_search ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("arguments", "user_texts", "expected"),
    [
        ({"query": "monitor"}, ["Quiero un monitor"], True),
        ({"query": "monitor"}, ["Quiero un monitor para trabajar, hasta 300"], False),
        ({"query": "monitor"}, ["Quiero un monitor para trabajar"], False),
        ({"query": "monitor", "category": "Monitors"}, ["Quiero un monitor"], False),
        ({"query": "monitor", "subcategory": "Gaming"}, ["Quiero un monitor"], False),
        ({"query": "monitor", "brand": "Acme"}, ["Quiero un monitor"], False),
        ({"query": "monitor", "min_price": 10}, ["Quiero un monitor"], False),
        ({"query": "monitor", "max_price": 10}, ["Quiero un monitor"], False),
        ({"query": "monitor", "category": None, "brand": None}, ["Quiero un monitor"], True),
        ({"query": "monitor"}, ["Quiero un", "monitor grande"], False),
        ({"query": "monitor"}, ["Hola buenas", "Quiero monitor"], False),
        ({"query": "monitor"}, ["monitor 4k"], False),
        ({"product_ids": ["MN-1", "MN-2"]}, ["Compará"], False),
        ({}, ["Hola"], False),
    ],
)
def test_too_vague_search(arguments, user_texts, expected):
    assert too_vague_search(arguments, user_texts) is expected


# --- leaked_tool_names ---------------------------------------------------------------------

NAMES = ["search_products", "start_checkout", "get_price"]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Estoy llamando a start_checkout.", ["start_checkout"]),
        ("Uso SEARCH_PRODUCTS y get_price", ["search_products", "get_price"]),
        ("(get_price)", ["get_price"]),
        ("my_get_price o get_prices", []),
        ("Hoy sale el precio, nada técnico.", []),
        ("", []),
    ],
)
def test_leaked_tool_names(text, expected):
    assert leaked_tool_names(text, NAMES) == expected


# --- numbers that cannot be compared must never crash a turn -----------------------------

HUGE = "9" * 40  # e.g. a pasted tracking code: too many digits for cents arithmetic


def test_a_huge_number_typed_by_the_customer_does_not_crash_the_price_filter_guard():
    assert ungrounded_price_filters({"max_price": 200}, [f"código {HUGE}"]) == ["max_price"]


def test_a_huge_number_typed_by_the_customer_does_not_crash_the_amount_check():
    assert ungrounded_amounts("Cuesta USD 200.", numbers_in_text(f"código {HUGE}")) == [D("200")]


@pytest.mark.parametrize("value", [float("inf"), float("-inf"), float("nan"), 1e400, 10**40])
def test_a_non_finite_or_absurd_price_filter_is_flagged_instead_of_crashing(value):
    assert ungrounded_price_filters({"max_price": value}, ["hasta 200 dólares"]) == ["max_price"]


def test_an_absurd_amount_in_the_reply_is_ungrounded_instead_of_crashing():
    reply = f"Cuesta USD {HUGE}."

    assert len(ungrounded_amounts(reply, {D("200")})) == 1


def test_a_huge_amount_in_the_allowed_numbers_is_ignored_not_fatal():
    assert ungrounded_amounts("Cuesta USD 200.", {D(HUGE), D("200")}) == []


# --- unknown product ids -------------------------------------------------------------------


@pytest.mark.parametrize("bad", ["MN-1", 5, {"a": 1}, None, [None, 3]])
def test_unknown_product_ids_ignores_a_malformed_product_ids_argument(bad):
    assert unknown_product_ids({"product_ids": bad}, set(), []) == []


def test_unknown_product_ids_flags_only_ids_nobody_returned_or_typed():
    arguments = {"product_ids": ["MN-1", "MN-2", "MN-3"]}

    assert unknown_product_ids(arguments, {"MN-1"}, ["comparame el MN-2"]) == ["MN-3"]


def test_a_typed_id_must_match_whole_not_as_part_of_another_id():
    assert unknown_product_ids({"product_id": "MN-1"}, set(), ["¿cuánto sale el MN-10?"]) == [
        "MN-1"
    ]


# --- negative quantities -------------------------------------------------------------------


@pytest.mark.parametrize(
    "message",
    ["Agregame -3 unidades del primero", "poné -2 del segundo", "agregá -1"],
)
def test_a_negative_number_in_the_message_is_a_negative_quantity(message):
    assert asks_for_negative_quantity(message) is True


@pytest.mark.parametrize(
    "message",
    [
        "Agregame 3 unidades del primero",
        "Agregá el MN-MON-0005, son 2",
        "Mostrame monitores de 24-27 pulgadas",
        "entre 100 - 200 dólares",
        "Agregá el primero",
    ],
)
def test_ids_ranges_and_plain_quantities_are_not_negative(message):
    assert asks_for_negative_quantity(message) is False
