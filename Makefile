.PHONY: up down logs migrate pull-models seed embed test test-backend test-frontend lint

up:            ## Start all services
	docker compose up -d --build

down:          ## Stop all services
	docker compose down

logs:
	docker compose logs -f

migrate:       ## Apply database migrations (Alembic) up to the latest revision
	docker compose exec backend alembic upgrade head

pull-models:   ## Download LLM and embedding models into Ollama
	docker compose exec ollama ollama pull $${LLM_MODEL:-qwen3:8b}
	docker compose exec ollama ollama pull $${EMBEDDING_MODEL:-nomic-embed-text}

seed:          ## Load the dataset into PostgreSQL and build embeddings (tasks DB-02 / AI-01)
	docker compose exec backend python -m app.scripts.seed

embed:         ## Embed products for semantic search; only new or changed ones (needs seed and pull-models)
	docker compose exec backend python -m app.scripts.embed

test: test-backend test-frontend

test-backend:
	docker compose exec backend pytest

test-frontend:
	cd frontend && npm test -- --run

lint:          ## Same checks as the CI lint steps
	docker compose exec backend ruff check .
	cd frontend && npm run lint && npm run typecheck
