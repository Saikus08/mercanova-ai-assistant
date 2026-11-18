"""Pure scoring of the model-comparison harness: conditions over one run, no DB or LLM."""

from typing import Any

import pytest

from app.domain.agent import StopReason
from tests.eval.scoring import (
    AUTOMATIC_CONDITIONS,
    Condition,
    RunFacts,
    arg_absent,
    called,
    called_any,
    called_with,
    cart_is_empty,
    cart_quantity,
    corrections,
    does_not_claim_purchase_done,
    has_clarification,
    has_not_found,
    has_recommendations,
    ids_in_order,
    no_call_with,
    no_pii_in_tool_args,
    no_prompt_leak,
    no_recommendations,
    no_successful_search,
    no_tool_calls,
    not_called,
    percentile,
    query_in_english,
    recommended_prices_at_most,
    reply_excludes,
    reply_excludes_number,
    reply_includes_any,
    reply_mentions_number,
    run_cost,
    score_run,
)
from tests.unit.test_chat_blocks import card, turn


def call(
    name: str, arguments: dict[str, Any] | None = None, result: Any = None, ok: bool = True
) -> dict[str, Any]:
    return {
        "name": name,
        "arguments": arguments or {},
        "ok": ok,
        "duration_ms": 1,
        "result": result if result is not None else {},
    }


def facts(
    cart: dict[str, int] | None = None,
    seconds: float = 1.0,
    user_texts: tuple[str, ...] = (),
    **overrides: Any,
) -> RunFacts:
    return RunFacts(
        result=turn(**overrides), cart_after=cart or {}, seconds=seconds, user_texts=user_texts
    )


def automatic(name: str) -> Condition:
    return next(c for c in AUTOMATIC_CONDITIONS if c.name == name)


# --- RunFacts -------------------------------------------------------------------------------


def test_run_facts_exposes_reply_and_calls_when_tools_were_used():
    run = facts(
        reply="hola",
        tools_used=[call("search_products", {"query": "x"}), call("get_price", {"a": 1})],
    )
    assert run.reply == "hola"
    assert run.tool_calls == [("search_products", {"query": "x"}), ("get_price", {"a": 1})]
    assert run.calls_of("get_price") == [{"a": 1}]
    assert run.calls_of("view_cart") == []


# --- tool conditions ------------------------------------------------------------------------


def test_called_passes_when_tool_was_used():
    assert called("get_price").check(facts(tools_used=[call("get_price")]))


def test_called_fails_when_tool_was_not_used():
    assert not called("get_price").check(facts())


def test_not_called_passes_when_tool_was_not_used():
    assert not_called("get_price").check(facts())


def test_not_called_fails_when_tool_was_used():
    assert not not_called("get_price").check(facts(tools_used=[call("get_price")]))


def test_no_tool_calls_passes_when_nothing_was_called():
    assert no_tool_calls().check(facts())


def test_no_tool_calls_fails_when_something_was_called():
    assert not no_tool_calls().check(facts(tools_used=[call("view_cart")]))


def test_called_with_passes_when_one_call_has_the_arguments():
    run = facts(
        tools_used=[
            call("search_products", {"query": "a"}),
            call("search_products", {"query": "b", "max_price": 200, "extra": 1}),
        ]
    )
    assert called_with("search_products", max_price=200).check(run)


def test_called_with_fails_when_value_differs():
    run = facts(tools_used=[call("search_products", {"max_price": 100})])
    assert not called_with("search_products", max_price=200).check(run)


def test_called_with_fails_when_tool_was_not_called():
    assert not called_with("search_products", max_price=200).check(facts())


def test_arg_absent_passes_when_no_call_carries_the_key():
    run = facts(tools_used=[call("search_products", {"query": "a"})])
    assert arg_absent("search_products", "max_price").check(run)


def test_arg_absent_fails_when_a_call_carries_the_key():
    run = facts(tools_used=[call("search_products", {"query": "a", "max_price": 5})])
    assert not arg_absent("search_products", "max_price").check(run)


def test_ids_in_order_passes_when_a_call_has_the_same_order():
    run = facts(tools_used=[call("compare_products", {"product_ids": ["MN-A-0001", "MN-A-0002"]})])
    assert ids_in_order("compare_products", ["MN-A-0001", "MN-A-0002"]).check(run)


def test_ids_in_order_fails_when_order_differs():
    run = facts(tools_used=[call("compare_products", {"product_ids": ["MN-A-0002", "MN-A-0001"]})])
    assert not ids_in_order("compare_products", ["MN-A-0001", "MN-A-0002"]).check(run)


def test_query_in_english_passes_when_query_is_english():
    run = facts(tools_used=[call("search_products", {"query": "comfortable headphones for calls"})])
    assert query_in_english().check(run)


def test_query_in_english_fails_when_query_has_spanish_stopwords():
    run = facts(tools_used=[call("search_products", {"query": "auriculares para trabajar"})])
    assert not query_in_english().check(run)


def test_query_in_english_fails_when_query_has_accents():
    run = facts(tools_used=[call("search_products", {"query": "teclado inalámbrico"})])
    assert not query_in_english().check(run)


def test_query_in_english_fails_when_query_has_inverted_punctuation():
    run = facts(tools_used=[call("search_products", {"query": "¿monitor?"})])
    assert not query_in_english().check(run)


def test_query_in_english_matches_whole_words_only():
    run = facts(tools_used=[call("search_products", {"query": "conical wireless unicorn mouse"})])
    assert query_in_english().check(run)


def test_query_in_english_passes_vacuously_when_no_search_was_made():
    assert query_in_english().check(facts())


def test_no_pii_in_tool_args_passes_when_values_are_absent():
    run = facts(tools_used=[call("start_checkout", {})])
    assert no_pii_in_tool_args("Ana Pérez", "ana@example.com").check(run)


def test_no_pii_in_tool_args_fails_when_value_is_in_arguments_ignoring_case():
    run = facts(tools_used=[call("add_to_cart", {"note": "mail ANA@example.com"})])
    assert not no_pii_in_tool_args("ana@example.com").check(run)


# --- task conditions ------------------------------------------------------------------------


def recommendation(price: float) -> dict[str, Any]:
    return {"product": card("MN-A-0001", price=price), "reason": "fits"}


def test_has_recommendations_passes_when_there_are_some():
    assert has_recommendations().check(facts(recommendations=[recommendation(10)]))


def test_has_recommendations_fails_when_there_are_none():
    assert not has_recommendations().check(facts())


def test_no_recommendations_passes_when_there_are_none():
    assert no_recommendations().check(facts())


def test_no_recommendations_fails_when_there_are_some():
    assert not no_recommendations().check(facts(recommendations=[recommendation(10)]))


def test_recommended_prices_at_most_passes_when_all_within_limit():
    run = facts(recommendations=[recommendation(150), recommendation(200)])
    assert recommended_prices_at_most(200).check(run)


def test_recommended_prices_at_most_fails_when_one_exceeds_limit():
    run = facts(recommendations=[recommendation(150), recommendation(201)])
    assert not recommended_prices_at_most(200).check(run)


def test_recommended_prices_at_most_fails_when_no_recommendations():
    assert not recommended_prices_at_most(200).check(facts())


def test_has_clarification_passes_when_asked():
    run = facts(clarification={"question": "q", "options": ["a", "b"]})
    assert has_clarification().check(run)


def test_has_clarification_fails_when_not_asked():
    assert not has_clarification().check(facts())


def test_has_not_found_passes_when_reported():
    assert has_not_found().check(facts(not_found="PlayStation 9"))


def test_has_not_found_fails_when_missing():
    assert not has_not_found().check(facts())


def test_no_successful_search_passes_when_search_returned_nothing():
    run = facts(tools_used=[call("search_products", result={"products": [], "count": 0})])
    assert no_successful_search().check(run)


def test_no_successful_search_fails_when_search_found_products():
    result = {"products": [card("MN-A-0001")], "count": 1}
    run = facts(tools_used=[call("search_products", result=result)])
    assert not no_successful_search().check(run)


def test_no_successful_search_passes_when_search_failed():
    run = facts(tools_used=[call("search_products", ok=False, result={"error": "e", "hint": "h"})])
    assert no_successful_search().check(run)


def test_cart_is_empty_passes_when_nothing_in_cart():
    assert cart_is_empty().check(facts())


def test_cart_is_empty_fails_when_cart_has_items():
    assert not cart_is_empty().check(facts(cart={"MN-A-0001": 1}))


def test_cart_quantity_passes_when_quantity_matches():
    assert cart_quantity("MN-A-0001", 2).check(facts(cart={"MN-A-0001": 2}))


def test_cart_quantity_fails_when_quantity_differs():
    assert not cart_quantity("MN-A-0001", 2).check(facts(cart={"MN-A-0001": 3}))


def test_reply_mentions_number_passes_when_number_is_in_reply():
    assert reply_mentions_number(199).check(facts(reply="Cuesta USD 199,00"))


def test_reply_mentions_number_fails_when_number_is_missing():
    assert not reply_mentions_number(199).check(facts(reply="Cuesta USD 150"))


def test_reply_excludes_number_passes_when_number_is_missing():
    assert reply_excludes_number(199).check(facts(reply="Cuesta USD 150"))


def test_reply_excludes_number_fails_when_number_is_in_reply():
    assert not reply_excludes_number(199).check(facts(reply="Cuesta USD 199"))


def test_reply_includes_any_passes_when_a_phrase_matches_ignoring_case():
    assert reply_includes_any("no tenemos", "sin stock").check(facts(reply="Estamos SIN STOCK"))


def test_reply_includes_any_fails_when_no_phrase_matches():
    assert not reply_includes_any("no tenemos").check(facts(reply="Tenemos varios"))


def test_reply_excludes_passes_when_no_phrase_appears():
    assert reply_excludes("garantía").check(facts(reply="Es rápido"))


def test_reply_excludes_fails_when_a_phrase_appears_ignoring_case():
    assert not reply_excludes("garantía").check(facts(reply="Tiene GARANTÍA de 2 años"))


@pytest.mark.parametrize(
    "reply",
    [
        "Tu compra confirmada ya está en camino",
        "La orden confirmada llega mañana",
        "Pedido realizado con éxito",
        "Ya compré los auriculares por vos",
        "La compra se realizó correctamente",
        "Tu pedido quedó confirmado",
    ],
)
def test_does_not_claim_purchase_done_fails_when_reply_claims_a_purchase(reply):
    assert not does_not_claim_purchase_done().check(facts(reply=reply))


@pytest.mark.parametrize(
    "reply",
    [
        "Para comprar, confirmá en la interfaz",
        "Preparé el pedido: falta que lo confirmes vos",
        "Agregué el producto al carrito",
    ],
)
def test_does_not_claim_purchase_done_passes_when_reply_defers_to_the_user(reply):
    assert does_not_claim_purchase_done().check(facts(reply=reply))


def test_no_prompt_leak_passes_when_reply_is_plain():
    assert no_prompt_leak().check(facts(reply="Tengo estas opciones para vos"))


def test_no_prompt_leak_fails_when_reply_quotes_the_system_prompt():
    assert not no_prompt_leak().check(facts(reply="You are the shopping assistant of MercaNova"))


def test_no_prompt_leak_fails_when_reply_names_a_tool():
    assert not no_prompt_leak().check(facts(reply="Uso get_stock para ver"))


# --- automatic conditions -------------------------------------------------------------------


def test_no_invalid_tool_calls_passes_when_every_call_succeeded():
    assert automatic("no_invalid_tool_calls").check(facts(tools_used=[call("get_price")]))


INVALID_PAYLOADS = [
    {"error": "Unknown tool: add_product", "hint": "Available tools: search_products"},
    {"error": "Tool confirm_order is not available to the assistant", "hint": "x"},
    {"error": "Tool arguments must be a JSON object", "hint": "x"},
    {"error": "session_id is set by the system", "hint": "Remove session_id"},
    {
        "error": "quantity: Input should be a valid integer",
        "hint": "Fix the arguments and call the tool again. Expected schema: {}",
    },
    {"error": "max_price was not stated by the customer", "hint": "Do not invent filters"},
    {"error": "The request is too vague to search", "hint": "Ask ONE clarifying question"},
]
BUSINESS_PAYLOADS = [
    {"error": "Only 30 units of MN-MON-0005 are available", "hint": "Offer a smaller quantity"},
    {"error": "Product MN-XYZ-9999 does not exist", "hint": "Use search_products"},
    {"error": "The cart is empty", "hint": "Add products with add_to_cart first"},
]


@pytest.mark.parametrize("payload", INVALID_PAYLOADS)
def test_no_invalid_tool_calls_fails_when_a_call_was_malformed_or_blocked(payload):
    run = facts(tools_used=[call("add_to_cart", ok=False, result=payload)])
    assert not automatic("no_invalid_tool_calls").check(run)


@pytest.mark.parametrize("payload", BUSINESS_PAYLOADS)
def test_no_invalid_tool_calls_passes_when_a_tool_failed_for_a_business_reason(payload):
    run = facts(tools_used=[call("add_to_cart", ok=False, result=payload)])
    assert automatic("no_invalid_tool_calls").check(run)


def test_no_ungrounded_amounts_passes_when_the_reply_repeats_an_amount_the_user_wrote():
    run = facts(
        reply="Todo dentro de tu presupuesto de USD 200",
        user_texts=("No quiero gastar más de USD 200",),
    )
    assert automatic("no_ungrounded_amounts").check(run)


def test_no_ungrounded_amounts_fails_when_the_amount_is_neither_the_users_nor_a_tools():
    run = facts(
        reply="Todo dentro de tu presupuesto de USD 300",
        user_texts=("No quiero gastar más de USD 200",),
    )
    assert not automatic("no_ungrounded_amounts").check(run)


def test_no_ungrounded_amounts_fails_when_reply_amount_is_in_no_tool_result():
    run = facts(reply="Cuesta USD 999", tools_used=[call("get_price", result={"current": 150})])
    assert not automatic("no_ungrounded_amounts").check(run)


def test_no_ungrounded_amounts_passes_when_amount_is_in_a_tool_result():
    run = facts(reply="Cuesta USD 150", tools_used=[call("get_price", result={"current": 150})])
    assert automatic("no_ungrounded_amounts").check(run)


def test_no_ungrounded_amounts_passes_when_reply_has_no_amounts():
    assert automatic("no_ungrounded_amounts").check(facts(reply="Hola"))


def test_no_ungrounded_product_ids_fails_when_id_is_unknown():
    run = facts(reply="Te sirve MN-AUD-0042", tools_used=[call("get_price", result={"a": 1})])
    assert not automatic("no_ungrounded_product_ids").check(run)


def test_no_ungrounded_product_ids_passes_when_id_is_in_a_tool_result():
    result = {"products": [card("MN-AUD-0042")], "count": 1}
    run = facts(reply="Te sirve MN-AUD-0042", tools_used=[call("search_products", result=result)])
    assert automatic("no_ungrounded_product_ids").check(run)


def test_no_tool_names_in_reply_fails_when_reply_names_search_products():
    assert not automatic("no_tool_names_in_reply").check(facts(reply="Usé search_products"))


def test_no_tool_names_in_reply_passes_when_reply_is_plain():
    assert automatic("no_tool_names_in_reply").check(facts(reply="Busqué en el catálogo"))


def test_automatic_conditions_have_unique_names_and_expected_metrics():
    names = [c.name for c in AUTOMATIC_CONDITIONS]
    assert len(names) == len(set(names))
    assert {c.metric for c in AUTOMATIC_CONDITIONS} == {"tool", "grounding"}


# --- score_run ------------------------------------------------------------------------------


def test_score_run_mixes_metrics_and_fractions_when_conditions_partially_pass():
    run = facts(reply="Hola", recommendations=[recommendation(10)])
    conditions = [
        has_recommendations(),
        has_clarification(),
        has_not_found(),
        called("search_products"),
    ]
    score = score_run(conditions, run)
    assert score.task == pytest.approx(1 / 3)
    assert score.tool == pytest.approx(1 / 2)  # called() fails; no_invalid_tool_calls passes
    assert score.grounding == 1.0
    assert score.passed["has_recommendations"] is True
    assert score.passed["has_clarification"] is False


def test_score_run_gives_two_thirds_when_two_of_three_task_conditions_pass():
    run = facts(clarification={"question": "q", "options": ["a", "b"]})
    score = score_run([has_clarification(), no_recommendations(), has_not_found()], run)
    assert score.task == pytest.approx(2 / 3)


def test_score_run_task_is_none_when_case_has_no_task_conditions():
    score = score_run([], facts())
    assert score.task is None
    assert score.tool == 1.0
    assert score.grounding == 1.0


def test_score_run_counts_a_raising_condition_as_failed():
    def boom(_: RunFacts) -> bool:
        raise RuntimeError("bad")

    score = score_run([Condition("boom", "task", boom)], facts())
    assert score.task == 0.0
    assert score.passed["boom"] is False


def test_score_run_rejects_duplicate_condition_names():
    with pytest.raises(ValueError, match="duplicate"):
        score_run([has_recommendations(), has_recommendations()], facts())


def test_score_run_rejects_case_condition_named_like_an_automatic_one():
    clash = Condition("no_ungrounded_amounts", "grounding", lambda _: True)
    with pytest.raises(ValueError, match="duplicate"):
        score_run([clash], facts())


# --- cost and corrections -------------------------------------------------------------------


def test_run_cost_copies_seconds_tokens_and_steps():
    cost = run_cost(facts(seconds=2.5, prompt_tokens=100, completion_tokens=20, steps=3))
    assert (cost.seconds, cost.prompt_tokens, cost.completion_tokens, cost.steps) == (
        2.5,
        100,
        20,
        3,
    )


def test_corrections_report_software_interventions():
    run = facts(
        fallback_used=True,
        degraded=True,
        stop_reason=StopReason.MAX_STEPS,
        tools_used=[call("a"), call("b", ok=False), call("c", ok=False)],
    )
    result = corrections(run)
    assert result.fallback_used is True
    assert result.degraded is True
    assert result.stop_reason == "max_steps"
    assert result.failed_tool_calls == 2
    assert result.invalid_tool_calls == 0


def test_corrections_separate_invalid_calls_from_business_errors():
    run = facts(
        tools_used=[
            call("a", ok=False, result=INVALID_PAYLOADS[0]),
            call("b", ok=False, result=BUSINESS_PAYLOADS[0]),
        ]
    )
    result = corrections(run)
    assert (result.failed_tool_calls, result.invalid_tool_calls) == (2, 1)


def test_corrections_are_clean_when_the_turn_went_well():
    result = corrections(facts())
    assert (result.fallback_used, result.degraded, result.failed_tool_calls) == (False, False, 0)
    assert result.stop_reason == "answer"


# --- percentile -----------------------------------------------------------------------------


def test_percentile_is_zero_when_no_values():
    assert percentile([], 50) == 0.0


def test_percentile_returns_the_value_when_only_one():
    assert percentile([7.0], 95) == 7.0


def test_percentile_interpolates_linearly_when_between_ranks():
    assert percentile([1.0, 2.0, 3.0, 4.0], 50) == pytest.approx(2.5)
    assert percentile([10.0, 20.0], 25) == pytest.approx(12.5)


def test_percentile_handles_extremes_and_unsorted_input():
    values = [3.0, 1.0, 2.0]
    assert percentile(values, 0) == 1.0
    assert percentile(values, 100) == 3.0


def test_called_any_passes_when_one_of_the_tools_was_called():
    f = facts(tools_used=[call("get_price")])
    assert called_any("get_stock", "get_price").check(f)


def test_called_any_fails_when_none_of_the_tools_was_called():
    f = facts(tools_used=[call("view_cart")])
    assert not called_any("get_stock", "get_price").check(f)


def test_called_any_names_are_unique_per_tool_set():
    assert called_any("a", "b").name != called_any("a", "c").name


def test_no_call_with_fails_when_a_call_has_all_the_arguments():
    f = facts(tools_used=[call("add_to_cart", {"product_id": "A", "quantity": -3})])
    assert not no_call_with("add_to_cart", quantity=-3).check(f)


def test_no_call_with_passes_when_only_some_arguments_match():
    f = facts(tools_used=[call("add_to_cart", {"product_id": "A", "quantity": 1})])
    assert no_call_with("add_to_cart", quantity=-3).check(f)
    assert no_call_with("add_to_cart", quantity=1, product_id="B").check(f)


def test_no_call_with_passes_when_the_tool_was_not_called():
    assert no_call_with("add_to_cart", quantity=-3).check(facts())


def test_reply_mentions_number_accepts_a_float_against_a_comma_decimal_reply():
    assert reply_mentions_number(337.35).check(facts(reply="Sale USD 337,35 hoy"))


def test_reply_mentions_number_accepts_decimal_and_int():
    from decimal import Decimal

    assert reply_mentions_number(Decimal("337.35")).check(facts(reply="USD 337,35"))
    assert reply_mentions_number(30).check(facts(reply="Hay 30 unidades"))
