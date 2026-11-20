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
| Agent (deterministic) | Agent loop with a **scripted model** returning prepared tool calls; assert tools executed and final answer grounded | pytest | `backend/tests/unit/test_agent_loop.py` (`ScriptedModel`) |
| Agent evaluation (non-deterministic) | The 20 golden cases against a real Ollama model, scored by task, tool and grounding; not blocking in CI | `python -m tests.eval.runner` | `backend/tests/eval/` |
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

Command (Ollama on, backend container up):

```bash
docker compose exec -T backend python -m tests.eval.runner --cases C04,C13 --model qwen3:8b --think false --runs 3
```

## Lessons from real use

1. **Prove the red.** After writing the test, run it and read why it fails. For a guard, also remove the guard line once and see the test fail. A test written together with its fix proves nothing until you do. A test for behavior that already worked has no red: say so in the PR.
2. **A prompt or tool-description change cannot be unit tested for behavior.** Test only that the text contains the rule, then measure with the runner. Change **one thing at a time** and re-measure the neighbors: one prompt rule fixed `C07` and broke `C08`, another dropped `C13` from 5/5 to 2/5.
3. **One run is noise.** Use at least 3 runs on the affected cases and a full sweep (2 runs) before opening the PR. Never claim a case is fixed from a single pass.
4. **Read the answers, not only the scores.** The scoring has biases (an id quoted from an earlier turn lowers grounding; blocked calls count as invalid). Open the JSON and read `reply` and `tools`.
5. **Do not change the scoring to make a result look better.** The published numbers in `docs/model-comparison.md` were measured with the current rules. Document the limit instead.
6. **Time and concurrency.** Use a fake clock for time budgets. For locks, use two real connections or threads; a lock on the test's own connection proves nothing.
7. **Check the model is running** before concluding a failure: an aborted run with `llm_unavailable` means Ollama is off, not a bug.

## Done when

`make test` is green and the PR description includes the test command output summary.
