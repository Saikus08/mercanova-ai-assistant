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
make up                  # levanta la base, Ollama, el backend y el frontend
make migrate             # crea las tablas en la base
make pull-models         # descarga el modelo de lenguaje y el de embeddings (solo la primera vez)
make seed                # carga el catálogo en la base
make embed               # genera los vectores de búsqueda; sin este paso el asistente no encuentra productos
```

Volver a correr `make seed` no pisa el stock que dejaron las compras confirmadas. Para restaurar las cantidades del Excel: `docker compose exec backend python -m app.scripts.seed --reset-stock`.

Antes de `make seed` hay que copiar el Excel de la cátedra (`MercaNova_dataset_obligatorio_2.xlsx`) en la carpeta `data/` de la raíz. El archivo no se guarda en el repositorio. El detalle de qué valida la carga está en `backend/README.md`, sección "Cargar el catálogo".

## Cómo probarlo

| Qué | Dónde |
|---|---|
| Aplicación (catálogo, carrito, historial) | http://localhost:5173 |
| Chat con el asistente, por texto o por voz | http://localhost:5173/chat |
| API del backend | http://localhost:8000 (documentación interactiva en `/docs`) |

- **Voz:** la primera transcripción descarga el modelo `small` de faster-whisper (unos 460 MB) y necesita internet. Las siguientes funcionan sin conexión. Se usa en Chrome, con permiso de micrófono.
- **Tests:** `make test` corre los del backend y los del frontend. `make lint` corre ruff, oxlint y el chequeo de tipos.
- **Casos de uso contra el modelo real:** `make eval` (no forma parte del CI). La comparación de modelos que justifica el modelo elegido está en [docs/model-comparison.md](docs/model-comparison.md).

## Ollama en la Mac: instalarlo directo es 30 veces más rápido

Dentro de Docker, Ollama corre solo en CPU. En una Mac con Apple Silicon medimos unos 1 token por segundo con un modelo de 8 mil millones de parámetros, y un turno del asistente tardaba varios minutos. Con Ollama instalado directo en la Mac, que usa la GPU, medimos unos 33 tokens por segundo y un turno de 8 a 11 segundos.

```bash
brew install ollama
OLLAMA_FLASH_ATTENTION=1 OLLAMA_KV_CACHE_TYPE=q8_0 ollama serve    # o: brew services start ollama
ollama pull qwen3:8b && ollama pull nomic-embed-text
docker compose stop ollama                                          # libera el puerto 11434
export OLLAMA_BASE_URL=http://host.docker.internal:11434
make up
```

Si no se instala nada, el `docker-compose.yml` levanta su propio Ollama y todo funciona igual, más lento. Por eso ese es el valor por defecto: quien clone el repositorio puede levantarlo sin instalar nada extra.

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
| `AGENT_TURN_TIMEOUT_SECONDS` | Tiempo máximo de un turno del asistente, revisado antes de cada llamada al modelo. Una llamada ya empezada no se interrumpe: termina por su propio límite | `90` |
| `AGENT_HISTORY_MESSAGES` | Cuántos mensajes anteriores recibe el modelo en cada turno | `8` |
| `LLM_TIMEOUT_SECONDS`, `LLM_TEMPERATURE`, `LLM_NUM_CTX` | Límite de espera por llamada al modelo, temperatura y tamaño de contexto | `120`, `0.1`, `8192` |
| `LLM_THINK` | Modo de razonamiento del modelo. Apagado por defecto: encendido, un turno tarda unos 52 s en vez de unos 14 s ([decisión 0011](docs/decisions/0011-chat-model.md)) | `false` |
| `SEARCH_MIN_SIMILARITY` | Similitud mínima para mostrar un resultado de búsqueda | `0.62` |
| `EMBEDDING_TIMEOUT_SECONDS`, `EMBEDDING_BATCH_SIZE` | Límite de espera y tamaño de lote al generar los vectores | `120`, `16` |
| `LLM_API_KEY` | Solo si se usa un proveedor pago | *(vacío)* |
| `STT_MODEL`, `STT_LANGUAGE` | Configuración de voz a texto | `small`, `es` |
| `DATASET_PATH` | Ruta del Excel de la cátedra dentro del contenedor | `/data/MercaNova_dataset_obligatorio_2.xlsx` |

## Cómo trabajamos

- **Reglas para el equipo y para el coding agent:** [AGENTS.md](AGENTS.md).
- **Skills del coding agent**, una por rol: backend, testing, frontend y revisión de código. Están en `.claude/skills/`.
- **Decisiones de diseño:** una por archivo en `docs/decisions/`, con alternativas, justificación y costos.
- **Casos de uso** que usamos para testear y para el video: [docs/use-cases.md](docs/use-cases.md).
- **Flujo de trabajo:** cada tarea es una issue de GitHub. Cada cambio entra por un pull request que revisa la otra persona del equipo.
