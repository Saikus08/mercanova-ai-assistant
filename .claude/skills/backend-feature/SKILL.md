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

## Done when

- Tests pass locally (`make test-backend`).
- New env vars documented, no secrets committed.
- PR opened with the template, linking the issue.
