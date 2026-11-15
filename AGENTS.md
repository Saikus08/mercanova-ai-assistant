# AGENTS.md — MercaNova AI Shopping Assistant

Rules for any coding agent (Claude Code, Codex, Cursor, Gemini CLI) working in this repository. Read this file before every task.

## Project

Prototype of an AI-assisted e-commerce for the fictional retailer MercaNova (ORT — Sistemas de Soporte de Decisión, Obligatorio 2). A user describes a need in natural language (text or voice), receives grounded recommendations, manages a cart and completes a fictitious purchase.

## Stack

| Layer | Technology |
|---|---|
| Frontend | React + Vite + TypeScript (`frontend/`) |
| Backend | Python 3.12 + FastAPI + Pydantic (`backend/`) |
| Database | PostgreSQL 16 + pgvector (relational + vector in one store) |
| LLM / embeddings | Ollama (local), provider configurable via env vars |
| Speech-to-text | faster-whisper (local) |
| Runtime | Docker Compose |

Decisions and their trade-offs live in `docs/decisions/` (ADRs). Do not change the stack without a new ADR.

## Repository layout

```
backend/      FastAPI app (hexagonal: domain / application / adapters)
frontend/     React app (design tokens + presentational components + containers)
docs/         ADRs, diagrams, model comparison, report assets
.claude/skills/  Reusable skills per role (see "Skills")
```

## Architecture rules (non-negotiable)

1. **Static vs dynamic data.** Static product content (descriptions, features, recommended_for, specs) may be retrieved via RAG. **Price, stock and order state must always come from a tool that reads the database in the current turn.** Never answer price/stock from embeddings, prompt context or model memory (RF-07, RF-18).
2. **No invented facts.** If a tool returns nothing, the assistant says it does not have that information.
3. **Sensitive actions need explicit user confirmation outside the LLM.** The checkout tool only creates a draft; confirming an order is a separate endpoint triggered by the user (RF-12).
4. **Hexagonal backend.** `domain/` has no imports from FastAPI, SQLAlchemy, Ollama or any adapter. Adapters implement ports defined in the domain/application layer.
5. **Frontend separation.** Colors, spacing and typography only via design tokens (`frontend/src/theme/tokens.ts`). Presentational components receive props and never fetch data; containers/hooks own data fetching.
6. **Stock changes are transactional.** Confirming an order decrements stock inside one DB transaction with row locking.
7. Single agent with tools. No multi-agent, no MCP (out of scope by assignment).

## Shopping assistant rules (the product's agent)

These rules apply to the code of the assistant itself (`backend/app/.../agent`, tools, prompts). The justification and sources for each one are in `docs/agent-practices.md`.

1. **Model proposes, software executes.** Before running a tool call the harness checks that the tool exists, validates the arguments against its schema and checks the permission table below. Invalid calls go back to the model as an actionable error (`{"error": ..., "hint": ...}`), never as an exception to the user.
2. **Tool permissions (least privilege).** `session_id` is always injected by the harness, never received from the model.

   | Tool | Permission |
   |---|---|
   | `search_products`, `get_product_details`, `get_price`, `get_stock`, `compare_products`, `get_alternatives`, `view_cart` | Free (read only) |
   | `add_to_cart` | Free, quantity validated against stock |
   | `start_checkout` | Creates a *pending* order only: no stock change, no purchase |
   | Confirm or cancel an order | **Not a tool.** Only the user, through the UI |

3. **State is explicit and separate from history.** The loop keeps a state object: user goal, candidate products already shown (with their ids, in order), tools used and current step. Memory across sessions is out of scope.
4. **Minimal context.** Send the model the system prompt, the state and a bounded window of recent messages, not the whole history.
5. **Stop conditions.** Stop when the answer is ready, at `AGENT_MAX_STEPS`, on a non-recoverable error, or when user confirmation is needed. Reaching the step limit returns a degraded but honest answer.
6. **Robustness.** Timeout on every LLM call, one retry for invalid tool arguments, and a clear fallback message if the model is unavailable.
7. **Guardrails.**
   - Input: politely refuse requests outside the store's domain.
   - Retrieved text (RAG) is wrapped as data, never followed as instructions (prompt injection).
   - Output: every price, stock figure and product id in the answer must come from a tool result of the current turn.
   - Personal data from checkout (name, email, address) never goes into prompts or logs.
8. **Prompting.** Low temperature, a system prompt with role, criteria and restrictions, and 2–3 few-shot examples (clarification, product not found).
9. **Observability.** Every chat turn has a trace id. Each step logs tool, arguments without personal data, duration, tokens and outcome.
10. **Evaluation.** Agent changes are checked against `docs/use-cases.md` with per-metric scores: task success, tool accuracy, grounding, cost and latency.

## Coding agent workflow

- **Tickets.** Every task given to a coding agent states context, goal, scope, **what is out of scope / must not be touched**, constraints and acceptance criteria (see the issue template).
- **Hooks.** `.claude/settings.json` runs `.claude/hooks/guard.py` before every edit or shell command. It blocks writing secret files, committing or pushing on `main`, force pushes and committing the dataset. Do not disable it to get around a block; fix the cause.
- **Review questions** in addition to the `code-review` skill: Did the agent invent architecture or data? Is there unnecessary complexity? Are the touched files reasonable for the ticket? Is the diff small enough to review? Would you merge it without reading it? If yes, read it. Does a new or changed flow have its diagram in `docs/diagrams/` in the same PR?
- Coding-agent skills (`.claude/skills/`) are procedures for building the project. They are not the assistant's tools.

## Configuration and secrets

- All configuration via environment variables. `.env.example` documents every variable; `.env` is git-ignored.
- Never commit secrets, API keys, `.env` files, model weights or the raw dataset dumps generated at runtime.

## Workflow

1. Every change starts from a GitHub issue (task ID like `BE-02`, `AI-03`).
2. Branch: `<type>/<task-id>-short-description` (e.g. `feat/be-02-cart-domain`).
3. Commits: Conventional Commits (`feat:`, `fix:`, `test:`, `docs:`, `refactor:`, `chore:`), referencing the issue (`feat(cart): add quantity update (#12)`). No AI attribution trailers.
4. Open a PR using the template. **The other team member reviews** using the `code-review` skill. No self-merge. The PR title and description are written in neutral Spanish; only the Conventional Commits prefix (e.g. `feat(catalog):`) stays in English.
5. A PR is mergeable only with tests passing and the PR checklist complete. The CI check shown in the PR must be green. The repository plan cannot enforce it, so the reviewer verifies it before approving.
6. When an architectural decision is made, add an ADR in `docs/decisions/` using `0000-template.md`.
7. When a change adds or modifies a flow (endpoint, use case, agent step), the same PR creates or updates its Mermaid diagram in `docs/diagrams/`, showing what is implemented. This builds the sequence diagrams the report needs as the project grows.

## Testing

- Backend: `pytest` — unit tests for domain (no DB, no LLM), integration tests for API + DB, agent tests with a mocked LLM.
- Frontend: Vitest + Testing Library for components and critical flows.
- Commands: `make test` (all), `make test-backend`, `make test-frontend`.
- Every bug fix includes a test that reproduces it.

## Linting

Backend: `ruff check` (config in `backend/pyproject.toml`). Frontend: `oxlint` and `tsc`. `make lint` runs both. `.pre-commit-config.yaml` runs them on commit (tests on push) and CI repeats them, so run `pre-commit install` once after cloning.

## Skills

| Skill | Role | Use when |
|---|---|---|
| `backend-feature` | Backend | Adding an endpoint, domain rule, repository or tool |
| `testing` | Backend/QA | Writing or fixing tests, agent evaluation cases |
| `frontend-component` | Frontend | Creating UI components or screens |
| `code-review` | Reviewer | Reviewing any PR before merge |

## Language

Code, identifiers, comments, commit messages and file and folder names (including `docs/diagrams/` and `docs/decisions/` files) in English. User-facing UI copy and assistant replies in Spanish (Rioplatense neutral). Documentation for reviewers (`docs/`, README, issues, PR descriptions) in neutral Spanish.

## Documentation rules

The reader is the professor grading the project. Every document, issue and PR must be understandable on its own.

1. Short, concrete sentences. Say what the thing does and why, not how we feel about it.
2. Never cite a requirement only by its code: write "explicit purchase confirmation (RF-12)", not just "RF-12".
3. Do not link to documents that do not exist yet or are incomplete, and do not use internal task IDs without saying what they are.
4. Every technology choice or claim about a tool cites a source (official docs, benchmark, repository) and compares at least one alternative.
5. Diagrams and screenshots must show what is actually implemented.
