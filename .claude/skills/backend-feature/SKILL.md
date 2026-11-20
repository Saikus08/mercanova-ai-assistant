---
name: backend-feature
description: Implement a backend feature (endpoint, domain rule, repository, or LLM tool) in the FastAPI hexagonal backend. Use for any task labeled area:backend or area:ai.
---

# Backend feature

## Before writing code

1. Read `AGENTS.md` and the linked GitHub issue. Identify the RF/RNF it covers and its acceptance criteria.
2. Locate the layer the change belongs to:
   - `backend/app/domain/` — entities, value objects, business rules (pure Python, no framework imports).
   - `backend/app/application/` — use cases and ports (interfaces).
   - `backend/app/adapters/` — FastAPI routers, SQLAlchemy repositories, Ollama client, STT, embeddings.
3. If the change introduces a new technology or pattern, stop and propose an ADR first.

## Implementation steps

1. Write the failing test first (`testing` skill): domain rule → unit test; endpoint → integration test.
2. Implement the domain/use case, then the adapter.
3. Validate inputs with Pydantic models; return typed responses.
4. Errors: raise domain exceptions (`ProductNotFound`, `InsufficientStock`, ...) and map them to HTTP codes in one exception handler. Never return raw 500s or stack traces.
5. Configuration only through `app/config.py` reading env vars; add new vars to `.env.example`.

## LLM tools (area:ai)

- Each tool = one use case + a JSON schema with typed, documented parameters.
- Tools that report price or stock must query the DB on every call. Never cache them in the prompt.
- Tool results are structured (dict/Pydantic), never free text.
- State-changing tools (cart, checkout) must be idempotent where possible; checkout only creates a draft.

## Agent loop and prompts (lessons from real use)

- **Enforce in software, not in the prompt.** A rule the model must follow (no invented filters, no negative quantities, ids only from tool results) goes into the loop or the dispatcher as a check that returns `{"error", "hint"}`. A prompt rule is a request: it can be ignored, and it shifts other behavior (a "buy" rule fixed `C07` but made the assistant search instead of ask in `C08`).
- **Validate model-written arguments defensively.** Our own guards run before the dispatcher validates the schema, so they must not crash on a wrong type (a number or a string where a list was expected).
- **Never echo values the model sent** in an error message: they may carry personal data. Name the field and the fix.
- **A row lock does not last a turn.** The cart tools commit in the middle of a turn and a commit releases row locks. Use an advisory lock on its own connection (decision 0012).
- **Dependency injection for time and randomness**: take the clock as a parameter so the test does not sleep.
- **Stage explicit paths** (`git add backend/app backend/tests/unit`), never `git add backend` or `-A`: evaluation runs leave JSON files in `backend/tests/eval/results/`.
- **A new or changed environment variable** goes into `config.py`, `.env.example` and `docker-compose.yml` (the backend only receives what the compose lists), and the container needs `docker compose up -d --build backend`.

## Done when

- Tests pass locally (`make test-backend`).
- New env vars documented, no secrets committed.
- PR opened with the template, linking the issue.
