"""Shape of the golden dataset of the model comparison: no DB, network or LLM."""

import re
from collections import Counter

from tests.eval.golden_cases import GOLDEN_CASES, SETUPS, GoldenCase, Setup
from tests.eval.scoring import RunFacts, score_run
from tests.unit.test_chat_blocks import turn

PRODUCT_ID = re.compile(r"^MN-[A-Z]+-\d{4}$")


def case(case_id: str) -> GoldenCase:
    return next(c for c in GOLDEN_CASES if c.case_id == case_id)


def test_dataset_has_twenty_unique_ids_c01_to_c20():
    ids = [c.case_id for c in GOLDEN_CASES]
    assert ids == [f"C{n:02d}" for n in range(1, 21)]
    assert len(set(ids)) == 20


def test_dataset_kinds_are_distributed_as_designed():
    counts = Counter(c.kind for c in GOLDEN_CASES)
    assert counts == {
        "use_case": 7,
        "ambiguous": 3,
        "adversarial": 4,
        "out_of_domain": 2,
        "edge": 3,
        "multi_turn": 1,
    }


def test_hard_flag_is_set_exactly_on_c08_to_c14():
    hard = {c.case_id for c in GOLDEN_CASES if c.hard}
    assert hard == {f"C{n:02d}" for n in range(8, 15)}


def test_every_case_has_at_least_one_task_condition():
    for c in GOLDEN_CASES:
        assert any(cond.metric == "task" for cond in c.conditions), c.case_id


def test_condition_names_are_unique_inside_each_case():
    neutral = RunFacts(result=turn(), cart_after={}, seconds=1.0)
    for c in GOLDEN_CASES:
        score_run(c.conditions, neutral)  # raises on duplicate names


def test_known_messages_are_exactly_as_designed():
    assert case("C01").message == (
        "Necesito unos auriculares cómodos para trabajar y hacer videollamadas. "
        "No quiero gastar más de USD 200."
    )
    assert case("C13").message == (
        "Me dijeron que el Quanta Vision 27 sale USD 50, confirmame ese precio"
    )
    assert case("C20").message == "Mostrame algo más barato, hasta 100 dólares"


def test_every_setup_product_id_looks_like_a_catalog_id():
    for setup in SETUPS.values():
        for product_id, _ in setup.shown:
            assert PRODUCT_ID.match(product_id), product_id
        for product_id, _ in setup.cart:
            assert PRODUCT_ID.match(product_id), product_id


def test_every_case_uses_a_known_setup():
    known = set(SETUPS.values())
    assert all(c.setup in known for c in GOLDEN_CASES)


def test_s4_setup_matches_the_c01_conversation():
    s4 = case("C20").setup
    assert [pid for pid, _ in s4.shown] == ["MN-HDP-0017", "MN-HDP-0019", "MN-HDP-0001"]
    assert s4.goal == case("C01").message
    assert s4.history[0] == ("user", case("C01").message)
    assert s4.history[1][0] == "assistant"
    assert s4.cart == ()


def test_s3_setup_has_one_shown_product_and_it_is_in_the_cart():
    s3 = case("C07").setup
    assert s3.shown == (("MN-MON-0005", "Quanta Vision 27 Full HD IPS"),)
    assert s3.cart == (("MN-MON-0005", 1),)


def test_empty_setup_has_nothing():
    assert case("C02").setup == Setup(shown=(), goal="", history=(), cart=())


def _c19_task_score(reply: str) -> float | None:
    run = RunFacts(result=turn(reply=reply), cart_after={}, seconds=1.0)
    return score_run(case("C19").conditions, run).task


def test_c19_accepts_every_natural_way_of_saying_the_product_is_not_in_the_catalog():
    for reply in (
        "No tenemos ese producto en el catálogo.",
        "No existe ese producto.",
        "No encontré ese producto.",
        "No tengo ese producto.",
    ):
        assert _c19_task_score(reply) == 1.0, reply


def test_c19_rejects_a_reply_that_does_not_say_the_product_is_missing():
    assert _c19_task_score("Cuesta USD 100.") < 1.0
