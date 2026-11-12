.PHONY: up down logs pull-models seed test test-backend test-frontend

up:            ## Start all services
	docker compose up -d --build

down:          ## Stop all services
	docker compose down

logs:
	docker compose logs -f

pull-models:   ## Download LLM and embedding models into Ollama
	docker compose exec ollama ollama pull $${LLM_MODEL:-qwen2.5:7b}
	docker compose exec ollama ollama pull $${EMBEDDING_MODEL:-nomic-embed-text}

seed:          ## Load the dataset into PostgreSQL and build embeddings (tasks DB-02 / AI-01)
	docker compose exec backend python -m app.scripts.seed

test: test-backend test-frontend

test-backend:
	docker compose exec backend pytest

test-frontend:
	cd frontend && npm test -- --run
