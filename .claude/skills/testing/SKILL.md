---
name: testing
description: Write or fix tests for the MercaNova backend and agent — unit, integration and LLM evaluation cases. Use whenever code changes behavior or a bug is reported.
---

# Testing

## Test pyramid for this project

| Level | Scope | Tools | Location |
|---|---|---|---|
| Unit | Domain rules (cart totals, stock validation, order state) | pytest | `backend/tests/unit/` |
| Integration | API + PostgreSQL (real DB in Docker) | pytest + httpx + compose test DB | `backend/tests/integration/` |
| Agent (deterministic) | Agent loop with a **mocked LLM** returning scripted tool calls; assert tools executed and final answer grounded | pytest | `backend/tests/agent/` |
| Agent evaluation (non-deterministic) | Fixed use cases against real Ollama models; not blocking in CI | pytest marker `eval` | `backend/tests/eval/` |
| Frontend | Components and critical flows | Vitest + Testing Library | `frontend/src/**/*.test.tsx` |

## Rules

1. Write the test before the fix/feature and see it fail.
2. One behavior per test; name it `test_<behavior>_when_<condition>`.
3. Unit tests never touch the DB, network or LLM.
4. Integration tests reset DB state per test (transaction rollback or truncate fixture).
5. Agent tests assert on **tool calls and data used**, not exact wording.
6. Always cover edge cases from the assignment: product not found, out of stock, quantity above availability, ambiguous query, empty audio, LLM unavailable.

## Evaluation cases (`eval`)

Use the canonical cases in `docs/use-cases.md`. For each model record: correct tool chosen, asked for clarification when needed, invented data (yes/no), latency. Results go to `docs/model-comparison.md`.

## Done when

`make test` is green and the PR description includes the test command output summary.
