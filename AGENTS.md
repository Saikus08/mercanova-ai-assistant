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

## Configuration and secrets

- All configuration via environment variables. `.env.example` documents every variable; `.env` is git-ignored.
- Never commit secrets, API keys, `.env` files, model weights or the raw dataset dumps generated at runtime.

## Workflow

1. Every change starts from a GitHub issue (task ID like `BE-02`, `AI-03`).
2. Branch: `<type>/<task-id>-short-description` (e.g. `feat/be-02-cart-domain`).
3. Commits: Conventional Commits (`feat:`, `fix:`, `test:`, `docs:`, `refactor:`, `chore:`), referencing the issue (`feat(cart): add quantity update (#12)`). No AI attribution trailers.
4. Open a PR using the template. **The other team member reviews** using the `code-review` skill. No self-merge.
5. A PR is mergeable only with tests passing and the PR checklist complete.
6. When an architectural decision is made, add an ADR in `docs/decisions/` using `0000-template.md`.

## Testing

- Backend: `pytest` — unit tests for domain (no DB, no LLM), integration tests for API + DB, agent tests with a mocked LLM.
- Frontend: Vitest + Testing Library for components and critical flows.
- Commands: `make test` (all), `make test-backend`, `make test-frontend`.
- Every bug fix includes a test that reproduces it.

## Skills

| Skill | Role | Use when |
|---|---|---|
| `backend-feature` | Backend | Adding an endpoint, domain rule, repository or tool |
| `testing` | Backend/QA | Writing or fixing tests, agent evaluation cases |
| `frontend-component` | Frontend | Creating UI components or screens |
| `code-review` | Reviewer | Reviewing any PR before merge |

## Language

Code, identifiers, comments and commit messages in English. User-facing UI copy and assistant replies in Spanish (Rioplatense neutral). Documentation for reviewers (`docs/`, README, issues, PR descriptions) in neutral Spanish.

## Documentation rules

The reader is the professor grading the project. Every document, issue and PR must be understandable on its own.

1. Short, concrete sentences. Say what the thing does and why, not how we feel about it.
2. Never cite a requirement only by its code: write "explicit purchase confirmation (RF-12)", not just "RF-12".
3. Do not link to documents that do not exist yet or are incomplete, and do not use internal task IDs without saying what they are.
4. Every technology choice or claim about a tool cites a source (official docs, benchmark, repository) and compares at least one alternative.
5. Diagrams and screenshots must show what is actually implemented.
