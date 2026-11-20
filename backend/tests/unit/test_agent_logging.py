"""What the agent loop may write to the logs about a tool call."""

import json

from app.application.agent.logging_args import loggable_arguments


def test_numbers_flags_and_product_ids_are_kept():
    arguments = {"max_price": 200, "in_stock_only": True, "product_id": "MN-DOC-0001"}

    assert loggable_arguments(arguments) == arguments


def test_free_text_is_replaced_by_its_length_because_it_may_hold_personal_data():
    logged = loggable_arguments({"query": "auriculares para Ana Pérez", "brand": "Echo"})

    assert logged == {"query": "<text 26 chars>", "brand": "<text 4 chars>"}


def test_lists_keep_product_ids_and_hide_other_text():
    logged = loggable_arguments({"product_ids": ["MN-MON-0005", "MN-MON-0001", "my address"]})

    assert logged == {"product_ids": ["MN-MON-0005", "MN-MON-0001", "<text 10 chars>"]}


def test_nested_values_are_not_expanded():
    assert loggable_arguments({"filters": {"a": "secret"}}) == {"filters": "<object>"}


def test_the_result_is_json_serializable():
    json.dumps(loggable_arguments({"query": "x", "quantity": 2, "ids": ["MN-1"]}))


def test_argument_names_that_are_not_plain_identifiers_are_hidden_too():
    logged = loggable_arguments({"query": "x", "Ana Pérez vive en Calle 1": 1})

    assert list(logged) == ["query", "<name>"]
