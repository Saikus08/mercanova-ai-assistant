#!/usr/bin/env python3
"""PreToolUse guard for coding agents working in this repository.

Blocks (exit code 2, reason on stderr):
1. Writing or editing secret files: `.env`, `.env.local`, `*.pem`, `*.key` (`.env.example` is allowed).
2. Committing or pushing directly on `main`.
3. Force pushes.
4. Committing the course dataset (`*.xlsx`) or anything under `data/` except `.gitkeep`.

Rationale: AGENTS.md "Configuration and secrets" and "Workflow"; course class 7 (p.13) on secrets
and auditing; assignment RNF-03 (no secrets in the repository).
"""
import json
import re
import subprocess
import sys

SECRET_FILE = re.compile(r"(^|/)(\.env(\.[\w-]+)?|[^/]+\.(pem|key))$")


def block(reason: str) -> None:
    print(f"Blocked by .claude/hooks/guard.py: {reason}", file=sys.stderr)
    sys.exit(2)


def current_branch() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
    except Exception:
        return ""


def main() -> None:
    try:
        event = json.load(sys.stdin)
    except json.JSONDecodeError:
        return
    tool = event.get("tool_name", "")
    data = event.get("tool_input", {}) or {}

    if tool in {"Write", "Edit", "MultiEdit", "NotebookEdit"}:
        path = data.get("file_path", "") or data.get("notebook_path", "")
        if SECRET_FILE.search(path) and not path.endswith(".env.example"):
            block(f"'{path}' may contain secrets. Document variables in .env.example instead.")
        return

    if tool == "Bash":
        cmd = data.get("command", "")
        if re.search(r"\bgit\s+push\b.*(\s--force\b|\s-f\b|\s--force-with-lease\b)", cmd):
            block("force push is not allowed; open a pull request instead.")
        if re.search(r"\bgit\s+(commit|push)\b", cmd) and current_branch() == "main":
            block("do not commit or push on main; create a branch and open a pull request.")
        if re.search(r"\bgit\s+add\b.*(\.xlsx\b|\bdata/(?!\.gitkeep))", cmd):
            block("the course dataset and files under data/ must not be committed.")


if __name__ == "__main__":
    main()
