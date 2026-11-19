"""Turns runner result files into the Markdown tables of the model comparison.

Usage: python -m tests.eval.report FILE... [--markdown]

Runs of the same (model, think) pair are merged across files. Everything here is pure: it only
reads the JSON files it is given.
"""

import argparse
import json
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

from tests.eval.scoring import percentile

GroupKey = tuple[str, bool | None]
THINK_LABELS = {None: "por defecto", True: "sí", False: "no"}


def format_number(value: float, digits: int = 2) -> str:
    """Decimal number with a comma as the separator."""
    return f"{value:.{digits}f}".replace(".", ",")


def format_percent(value: float | None) -> str:
    return "-" if value is None else f"{format_number(value * 100, 1)} %"


def load_files(paths: Iterable[Path | str]) -> list[tuple[GroupKey, list[dict[str, Any]]]]:
    """One (group key, run records) pair per file."""
    loaded = []
    for path in paths:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        records = [run for case in data["cases"] for run in case["runs"]]
        loaded.append(((data["model"], data["think"]), records))
    return loaded


def group_runs(
    loaded: Iterable[tuple[GroupKey, list[dict[str, Any]]]],
) -> dict[GroupKey, list[dict[str, Any]]]:
    groups: dict[GroupKey, list[dict[str, Any]]] = {}
    for key, records in loaded:
        groups.setdefault(key, []).extend(records)
    return groups


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    ok = [r for r in records if not r["error"]]
    task = [r["scores"]["task"] for r in ok if r["scores"]["task"] is not None]
    seconds = [r["cost"]["seconds"] for r in ok]
    return {
        "runs": len(records),
        "error_runs": len(records) - len(ok),
        "task": _mean(task),
        "tool": _mean([r["scores"]["tool"] for r in ok]),
        "grounding": _mean([r["scores"]["grounding"] for r in ok]),
        "seconds_mean": _mean(seconds),
        "seconds_p50": percentile(seconds, 50) if seconds else None,
        "seconds_p95": percentile(seconds, 95) if seconds else None,
        "prompt_tokens": _mean([r["cost"]["prompt_tokens"] for r in ok]),
        "completion_tokens": _mean([r["cost"]["completion_tokens"] for r in ok]),
        "steps": _mean([r["cost"]["steps"] for r in ok]),
        "fallback_runs": sum(r["corrections"]["fallback_used"] for r in ok),
        "degraded_runs": sum(r["corrections"]["degraded"] for r in ok),
        "invalid_calls": sum(r["corrections"]["invalid_tool_calls"] for r in ok),
    }


def _is_full_pass(record: dict[str, Any]) -> bool:
    scores = record["scores"]
    return not record["error"] and (scores["task"], scores["tool"], scores["grounding"]) == (
        1.0,
        1.0,
        1.0,
    )


def case_matrix(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Per case: full passes, total runs (errors count as not passed) and mean task."""
    by_case: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        by_case.setdefault(record["case_id"], []).append(record)
    return {
        case_id: {
            "passed": sum(_is_full_pass(r) for r in runs),
            "total": len(runs),
            "task_mean": _mean(
                [
                    r["scores"]["task"]
                    for r in runs
                    if not r["error"] and r["scores"]["task"] is not None
                ]
            ),
        }
        for case_id, runs in sorted(by_case.items())
    }


def _table(headers: list[str], rows: list[list[str]]) -> list[str]:
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    lines += ["| " + " | ".join(row) + " |" for row in rows]
    return lines


def _optional(value: float | None, digits: int) -> str:
    return "-" if value is None else format_number(value, digits)


def _summary_row(key: GroupKey, summary: dict[str, Any]) -> list[str]:
    model, think = key
    seconds = " / ".join(
        _optional(summary[name], 1) for name in ("seconds_mean", "seconds_p50", "seconds_p95")
    )
    tokens = (
        f"{_optional(summary['prompt_tokens'], 0)} / {_optional(summary['completion_tokens'], 0)}"
        f" ({_optional(summary['steps'], 1)} pasos)"
    )
    corrections = (
        f"fallback: {summary['fallback_runs']}, degradadas: {summary['degraded_runs']}, "
        f"llamadas inválidas: {summary['invalid_calls']}, errores: {summary['error_runs']}"
    )
    return [
        model,
        THINK_LABELS[think],
        format_percent(summary["task"]),
        format_percent(summary["tool"]),
        format_percent(summary["grounding"]),
        seconds,
        tokens,
        corrections,
    ]


def _cell(entry: dict[str, Any] | None) -> str:
    if entry is None:
        return "-"
    text = f"{entry['passed']}/{entry['total']}"
    if entry["passed"] != entry["total"] and entry["task_mean"] is not None:
        text += f" ({format_number(entry['task_mean'])})"
    return text


def render_markdown(groups: dict[GroupKey, list[dict[str, Any]]]) -> str:
    keys = sorted(groups, key=lambda key: (key[0], THINK_LABELS[key[1]]))
    summary_headers = [
        "Modelo",
        "Razonamiento",
        "Task Success",
        "Tool Accuracy",
        "Grounding",
        "Segundos (media / p50 / p95)",
        "Tokens",
        "Correcciones del software",
    ]
    summary_rows = [_summary_row(key, summarize(groups[key])) for key in keys]
    matrices = {key: case_matrix(groups[key]) for key in keys}
    case_ids = sorted({case_id for matrix in matrices.values() for case_id in matrix})
    matrix_headers = ["Caso"] + [
        f"{model} (razonamiento: {THINK_LABELS[think]})" for model, think in keys
    ]
    matrix_rows = [
        [case_id] + [_cell(matrices[key].get(case_id)) for key in keys] for case_id in case_ids
    ]
    lines = [
        "## Resumen por modelo",
        "",
        *_table(summary_headers, summary_rows),
        "",
        "## Resultado por caso (aprobadas / corridas; entre paréntesis, Task Success medio)",
        "",
        *_table(matrix_headers, matrix_rows),
    ]
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tests.eval.report", description=__doc__)
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument("--markdown", action="store_true", help="Markdown output (the default)")
    args = parser.parse_args(argv)
    print(render_markdown(group_runs(load_files(args.files))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
