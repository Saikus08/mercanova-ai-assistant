# ADR-0001: Technology stack

- **Status:** accepted
- **Date:** 2026-11-12
- **Owner:** Team (Grupo 8, N8B)
- **Related:** RNF-01, RNF-02, RNF-03, RNF-06

## Problem
We need a full-stack prototype (frontend, backend, persistence, LLM, speech-to-text) that runs locally and reproducibly with Docker, can be built by a team of two in about four weeks, and makes the AI architecture easy to explain.

## Alternatives considered
| Concern | Options |
|---|---|
| Backend | FastAPI (Python) · Node/Express (TypeScript) · .NET |
| Database | PostgreSQL + pgvector · PostgreSQL + separate vector DB (Chroma/Qdrant) · SQLite + FAISS |
| LLM | Ollama (local) · OpenAI/Anthropic API |
| Frontend | React + Vite · Next.js · Streamlit |
| STT | faster-whisper (local) · Browser Web Speech API · cloud STT |

## Decision
React + Vite + TypeScript · FastAPI · PostgreSQL 16 + pgvector · Ollama · faster-whisper · Docker Compose.

## Justification
- **FastAPI:** the LLM, embeddings and Whisper ecosystem is Python-first; Pydantic gives typed schemas reused for tool definitions and structured outputs; automatic OpenAPI docs.
- **PostgreSQL + pgvector:** one store for transactional data (stock, orders, with row locks) and vector search; hybrid queries (semantic + SQL filters on price/category) in a single query; one container fewer.
- **Ollama:** free, local, no secrets to manage, recommended by the course; allows comparing several open models with tool calling. Provider stays configurable via env vars.
- **React + Vite:** a real application UI (not a notebook/Streamlit demo), fast dev server, component model fits design tokens + container/presentational split.
- **faster-whisper:** local, works offline, good Spanish accuracy with the `small` model; avoids browser-specific STT support.

## Trade-offs
- Local models are slower and less accurate at tool calling than frontier APIs; mitigated by strict tool schemas, guardrails and model comparison.
- pgvector scales worse than a dedicated vector DB at millions of vectors; irrelevant at 360 products.
- Two languages (Python + TypeScript) in one repo; mitigated by clear folder ownership and per-role skills.
- Running Ollama + Whisper locally needs about 8 GB RAM; documented in the README.
