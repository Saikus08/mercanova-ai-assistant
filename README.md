# MercaNova AI Shopping Assistant

Prototipo de e-commerce con asistente de inteligencia artificial para la empresa ficticia MercaNova.
Universidad ORT Uruguay, Sistemas de Soporte de Decisión, Obligatorio 2. Grupo 8 (N8B): Agustín Vignolo y Florencia Mendoza.

El usuario describe lo que necesita en lenguaje natural, por texto o por voz. El asistente busca en el catálogo, recomienda productos explicando por qué, compara opciones y ayuda a completar una compra ficticia. Los precios y el stock que muestra siempre salen de la base de datos.

## Tecnologías

React + Vite (frontend) · FastAPI (backend) · PostgreSQL con pgvector · Ollama (modelo de lenguaje local) · faster-whisper (voz a texto) · Docker Compose.

La justificación de cada elección, con alternativas y fuentes, está en [Decisión 0001: Tecnologías de la solución](docs/decisions/0001-stack.md).

## Cómo levantarlo

Requisitos: Docker Desktop con al menos 8 GB de memoria asignada.

```bash
cp .env.example .env     # configuración local; los valores por defecto funcionan
make up                  # levanta todos los servicios
make migrate             # crea las tablas en la base
make pull-models         # descarga el modelo de lenguaje y el de embeddings (solo la primera vez)
make seed                # carga el catálogo en la base
```

Antes de `make seed` hay que copiar el Excel de la cátedra (`MercaNova_dataset_obligatorio_2.xlsx`) en la carpeta `data/` de la raíz. El archivo no se guarda en el repositorio. El detalle de qué valida la carga está en `backend/README.md`, sección "Cargar el catálogo".

> **Estado actual:** hoy el compose levanta solo la base de datos y Ollama. Esta sección se completa cuando estén el backend y el frontend.

## Variables de entorno

Toda la configuración se lee de variables de entorno. Ningún secreto se guarda en el repositorio.

| Variable | Para qué sirve | Valor de ejemplo |
|---|---|---|
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | Credenciales de la base | `mercanova`, `change-me`, `mercanova` |
| `POSTGRES_PORT` | Puerto local de la base | `5432` |
| `DATABASE_URL` | Conexión que usa el backend | `postgresql+psycopg://mercanova:change-me@db:5432/mercanova` |
| `LLM_PROVIDER` | Proveedor del modelo de lenguaje | `ollama` |
| `OLLAMA_BASE_URL`, `OLLAMA_PORT` | Dirección de Ollama | `http://ollama:11434`, `11434` |
| `LLM_MODEL` | Modelo de chat (tiene que soportar herramientas) | `qwen3:8b` |
| `EMBEDDING_MODEL` | Modelo para la búsqueda por significado | `nomic-embed-text` |
| `AGENT_MAX_STEPS` | Máximo de llamadas a herramientas por respuesta | `6` |
| `LLM_API_KEY` | Solo si se usa un proveedor pago | *(vacío)* |
| `STT_MODEL`, `STT_LANGUAGE` | Configuración de voz a texto | `small`, `es` |
| `DATASET_PATH` | Ruta del Excel de la cátedra dentro del contenedor | `/data/MercaNova_dataset_obligatorio_2.xlsx` |

## Cómo trabajamos

- **Reglas para el equipo y para el coding agent:** [AGENTS.md](AGENTS.md).
- **Skills del coding agent**, una por rol: backend, testing, frontend y revisión de código. Están en `.claude/skills/`.
- **Decisiones de diseño:** una por archivo en `docs/decisions/`, con alternativas, justificación y costos.
- **Casos de uso** que usamos para testear y para el video: [docs/use-cases.md](docs/use-cases.md).
- **Flujo de trabajo:** cada tarea es una issue de GitHub. Cada cambio entra por un pull request que revisa la otra persona del equipo.
