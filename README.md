# MercaNova AI Shopping Assistant

AI-assisted e-commerce prototype for the fictional retailer MercaNova. Universidad ORT Uruguay, Sistemas de Soporte de Decisión, Obligatorio 2 (Grupo 8, N8B).

A user describes what they need in natural language (text or voice), receives grounded product recommendations, compares options, manages a cart and completes a fictitious purchase.

## Stack

React + Vite (frontend) · FastAPI (backend) · PostgreSQL + pgvector · Ollama · faster-whisper · Docker Compose. Rationale in [ADR-0001](docs/decisions/0001-stack.md).

## Run locally

Requirements: Docker Desktop with at least 8 GB of RAM assigned.

```bash
cp .env.example .env          # adjust values if needed
make up                       # start services
make pull-models              # download LLM + embedding models (first time only)
make seed                     # load the dataset and build embeddings
```

> Run instructions will be completed as backend (BE-01) and frontend (FE-01) are scaffolded.

## Environment variables

All configuration is read from environment variables; `.env.example` lists them. Secrets are never committed.

| Variable | Purpose | Example |
|---|---|---|
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | Database credentials | `mercanova` / `change-me` / `mercanova` |
| `POSTGRES_PORT` | Host port for PostgreSQL | `5432` |
| `DATABASE_URL` | Backend connection string | `postgresql+psycopg://mercanova:change-me@db:5432/mercanova` |
| `LLM_PROVIDER` | `ollama` (default) or a hosted provider | `ollama` |
| `OLLAMA_BASE_URL` / `OLLAMA_PORT` | Ollama endpoint | `http://ollama:11434` / `11434` |
| `LLM_MODEL` | Chat model with tool calling | `qwen2.5:7b` |
| `EMBEDDING_MODEL` | Embedding model | `nomic-embed-text` |
| `AGENT_MAX_STEPS` | Max tool-calling iterations per turn | `6` |
| `LLM_API_KEY` | Only for hosted providers | *(empty)* |
| `STT_MODEL` / `STT_LANGUAGE` | faster-whisper settings | `small` / `es` |
| `DATASET_PATH` | Path to the course dataset inside the container | `/data/MercaNova_dataset_obligatorio_2.xlsx` |

## How we work

- Rules for humans and coding agents: [AGENTS.md](AGENTS.md)
- Skills per role: `.claude/skills/` (`backend-feature`, `testing`, `frontend-component`, `code-review`)
- Decisions: `docs/decisions/` (ADRs)
- Use cases for tests and the demo: [docs/use-cases.md](docs/use-cases.md)
- Every task is a GitHub issue, every change a reviewed PR (template in `.github/`).
