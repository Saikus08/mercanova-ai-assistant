"""Report of the model comparison from fabricated result files: no DB, network or LLM."""

import json
from pathlib import Path
from typing import Any

import pytest

from tests.eval.report import (
    case_matrix,
    format_number,
    group_runs,
    load_files,
    main,
    render_markdown,
    summarize,
)


def run_record(
    case_id: str = "C01",
    scores: tuple[float, float, float] = (1.0, 1.0, 1.0),
    seconds: float = 2.0,
    prompt: int = 100,
    completion: int = 10,
    steps: int = 2,
    fallback: bool = False,
    degraded: bool = False,
    invalid: int = 0,
) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "kind": "use_case",
        "run": 1,
        "error": None,
        "scores": {"task": scores[0], "tool": scores[1], "grounding": scores[2]},
        "conditions": {},
        "cost": {
            "seconds": seconds,
            "prompt_tokens": prompt,
            "completion_tokens": completion,
            "steps": steps,
        },
        "corrections": {
            "fallback_used": fallback,
            "degraded": degraded,
            "stop_reason": "answer",
            "failed_tool_calls": invalid,
            "invalid_tool_calls": invalid,
        },
        "reply": "x",
        "tools": [],
        "cart_after": {},
    }


def error_record(case_id: str = "C01") -> dict[str, Any]:
    return {
        "case_id": case_id,
        "kind": "use_case",
        "run": 1,
        "error": "RuntimeError: boom",
        "scores": {"task": None, "tool": None, "grounding": None},
        "conditions": {},
        "cost": None,
        "corrections": None,
        "reply": None,
        "tools": [],
        "cart_after": {},
    }


def write_file(path: Path, model: str, think: bool | None, records: list[dict[str, Any]]) -> Path:
    cases: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        cases.setdefault(record["case_id"], []).append(record)
    data = {
        "model": model,
        "think": think,
        "temperature": 0.1,
        "num_ctx": 8192,
        "runs": 3,
        "label": None,
        "started_at": "2026-05-17T14:30:05+00:00",
        "cases": [
            {"case_id": cid, "kind": "use_case", "hard": False, "runs": runs}
            for cid, runs in cases.items()
        ],
    }
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_format_number_uses_a_comma_as_decimal_separator():
    assert format_number(0.6667) == "0,67"
    assert format_number(12.0, digits=1) == "12,0"
    assert format_number(1234.0, digits=0) == "1234"


def test_load_files_flattens_runs_and_groups_by_model_and_think(tmp_path):
    a = write_file(tmp_path / "a.json", "m1", False, [run_record("C01"), run_record("C02")])
    b = write_file(tmp_path / "b.json", "m1", True, [run_record("C01")])
    c = write_file(tmp_path / "c.json", "m1", False, [run_record("C03")])

    groups = group_runs(load_files([a, b, c]))

    assert sorted(groups) == [("m1", False), ("m1", True)]
    assert [r["case_id"] for r in groups[("m1", False)]] == ["C01", "C02", "C03"]
    assert len(groups[("m1", True)]) == 1


def test_summarize_means_scores_over_non_error_runs():
    records = [
        run_record(scores=(1.0, 1.0, 1.0)),
        run_record(scores=(0.5, 0.0, 1.0)),
        error_record(),
    ]

    summary = summarize(records)

    assert summary["task"] == 0.75
    assert summary["tool"] == 0.5
    assert summary["grounding"] == 1.0
    assert summary["runs"] == 3
    assert summary["error_runs"] == 1


def test_summarize_excludes_none_task_from_the_task_mean():
    none_task = run_record()
    none_task["scores"]["task"] = None

    summary = summarize([none_task, run_record(scores=(0.5, 1.0, 1.0))])

    assert summary["task"] == 0.5
    assert summary["tool"] == 1.0


def test_summarize_cost_has_mean_p50_p95_and_token_and_step_means():
    records = [
        run_record(seconds=s, prompt=p, completion=c, steps=st)
        for s, p, c, st in [(1.0, 100, 10, 1), (2.0, 200, 20, 2), (3.0, 300, 30, 3)]
    ]

    summary = summarize(records)

    assert summary["seconds_mean"] == 2.0
    assert summary["seconds_p50"] == 2.0
    assert summary["seconds_p95"] == pytest.approx(2.9)
    assert summary["prompt_tokens"] == 200
    assert summary["completion_tokens"] == 20
    assert summary["steps"] == 2


def test_summarize_counts_corrections():
    records = [
        run_record(fallback=True, invalid=2),
        run_record(degraded=True, invalid=1),
        run_record(),
        error_record(),
    ]

    summary = summarize(records)

    assert summary["fallback_runs"] == 1
    assert summary["degraded_runs"] == 1
    assert summary["invalid_calls"] == 3
    assert summary["error_runs"] == 1


def test_summarize_a_group_with_only_errors_has_no_means():
    summary = summarize([error_record()])

    assert summary["task"] is None
    assert summary["tool"] is None
    assert summary["seconds_mean"] is None


def test_case_matrix_counts_full_passes_over_all_runs():
    records = [
        run_record("C01"),
        run_record("C01", scores=(0.5, 1.0, 1.0)),
        run_record("C01", scores=(1.0, 1.0, 0.5)),
        error_record("C02"),
        run_record("C02"),
    ]

    matrix = case_matrix(records)

    assert matrix["C01"] == {"passed": 1, "total": 3, "task_mean": (1.0 + 0.5 + 1.0) / 3}
    assert matrix["C02"] == {"passed": 1, "total": 2, "task_mean": 1.0}


def test_render_markdown_has_spanish_headers_and_a_summary_row(tmp_path):
    path = write_file(
        tmp_path / "a.json", "qwen3:8b", None, [run_record(scores=(0.8, 0.9, 1.0), seconds=2.5)]
    )

    text = render_markdown(group_runs(load_files([path])))

    for header in (
        "Modelo",
        "Razonamiento",
        "Task Success",
        "Tool Accuracy",
        "Grounding",
        "Segundos (media / p50 / p95)",
        "Tokens",
        "Correcciones del software",
    ):
        assert header in text
    assert "qwen3:8b" in text
    assert "80,0 %" in text
    assert "2,5 / 2,5 / 2,5" in text


def test_render_markdown_matrix_shows_k_of_n_and_mean_task_when_not_perfect(tmp_path):
    a = write_file(
        tmp_path / "a.json",
        "m1",
        False,
        [run_record("C01")] * 3
        + [run_record("C02")]
        + [run_record("C02", scores=(0.0, 1.0, 1.0))] * 2,
    )
    b = write_file(tmp_path / "b.json", "m2", True, [run_record("C01")])

    text = render_markdown(group_runs(load_files([a, b])))

    assert "3/3" in text
    assert "1/3 (0,33)" in text
    assert "| C01 |" in text
    assert "| C02 |" in text


def test_main_prints_markdown_for_the_given_files(tmp_path, capsys):
    path = write_file(tmp_path / "a.json", "m1", None, [run_record()])

    assert main([str(path), "--markdown"]) == 0

    assert "Modelo" in capsys.readouterr().out
