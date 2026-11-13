# Backend

API de MercaNova, escrita en Python 3.12 con FastAPI. Guarda los datos en PostgreSQL con la extensión pgvector. Corre dentro de Docker: no hace falta instalar Python en la máquina.

## Estructura

El código sigue una arquitectura hexagonal. Las reglas de negocio no dependen de la base de datos ni del framework web, así que se pueden probar sin levantar ninguno de los dos.

```
backend/
├── app/
│   ├── domain/            Reglas y valores del negocio (Python puro, sin FastAPI ni SQLAlchemy)
│   ├── application/       Casos de uso y puertos (interfaces que implementan los adaptadores)
│   ├── adapters/
│   │   ├── api/           Rutas HTTP de FastAPI
│   │   ├── dataset/       Lectura y validación del Excel de la cátedra
│   │   └── persistence/   Modelos de tablas (SQLAlchemy), sesión de base de datos, carga del catálogo
│   ├── scripts/           Scripts de consola (carga del catálogo)
│   ├── config.py          Configuración leída de variables de entorno
│   └── main.py            Crea la aplicación FastAPI
├── migrations/            Migraciones de Alembic (cambios de esquema versionados)
├── tests/
│   ├── unit/              Sin base de datos ni red
│   └── integration/       Contra PostgreSQL real en Docker
├── alembic.ini
├── Dockerfile
├── requirements.txt       Dependencias de ejecución, con versión fija
└── requirements-dev.txt   Dependencias de test (pytest, httpx)
```

El modelo de datos, con el diagrama de tablas, está en `docs/diagrams/modelo-de-datos.md`.

## Variables de entorno

| Variable | Para qué sirve | Valor en Docker Compose |
|---|---|---|
| `DATABASE_URL` | Conexión a PostgreSQL, con el driver psycopg 3 | `postgresql+psycopg://<POSTGRES_USER>:<POSTGRES_PASSWORD>@db:5432/<POSTGRES_DB>` |
| `OLLAMA_BASE_URL` | Dirección del servidor de modelos de lenguaje | `http://ollama:11434` |
| `DATASET_PATH` | Ruta del Excel de la cátedra dentro del contenedor | `/data/MercaNova_dataset_obligatorio_2.xlsx` |
| `TEST_DATABASE_NAME` | Nombre de la base que crean los tests (opcional) | `mercanova_test` |

Docker Compose arma `DATABASE_URL` a partir de `POSTGRES_USER`, `POSTGRES_PASSWORD` y `POSTGRES_DB`. Si la contraseña tiene caracteres especiales como `@`, `:` o `/`, hay que escribirlos codificados para URL (por ejemplo `@` como `%40`).

## Cómo levantarlo

Desde la raíz del repositorio:

```bash
docker compose up -d --build db backend   # base de datos + API
make migrate                              # crea las tablas (alembic upgrade head)
curl localhost:8000/api/health            # {"status":"ok","db":"ok","llm":"unknown","stt":"unknown"}
```

El código se monta dentro del contenedor y uvicorn se reinicia solo al guardar un archivo. La documentación interactiva de la API queda en `http://localhost:8000/docs`.

`/api/health` responde siempre con `status: "ok"` mientras la API funcione, e informa el estado de cada servicio por separado. Si la base no responde, devuelve `db: "down"` en lugar de un error. Los campos `llm` y `stt` valen `"unknown"` hasta que se agreguen esos servicios.

## Cargar el catálogo

El catálogo sale del Excel que entrega la cátedra (`MercaNova_dataset_obligatorio_2.xlsx`). El archivo no se guarda en el repositorio: cada persona lo copia en la carpeta `data/` de la raíz. Docker Compose monta esa carpeta en el contenedor del backend como `/data`, en modo solo lectura.

```bash
cp <ruta-al-excel>/MercaNova_dataset_obligatorio_2.xlsx data/
make migrate      # las tablas tienen que existir antes de cargar
make seed         # o: docker compose exec backend python -m app.scripts.seed
```

El script lee las ocho hojas del Excel: marcas, categorías, depósitos, productos, especificaciones, relaciones entre productos, precios y stock. Valida cada fila antes de escribirla:

- Los campos obligatorios tienen valor y cada columna tiene el tipo esperado (número, fecha, sí/no).
- Las columnas con listas (`recommended_for`, `not_recommended_for`, `key_features`, `tags`) se separan por `;` y se quitan los espacios sobrantes.
- Los rangos son válidos: precios mayores o iguales a 0, descuento entre 0 y 100, cantidades de stock mayores o iguales a 0, calificación entre 0 y 5, fuerza de una relación entre 0 y 1.
- Las referencias existen: la marca y la categoría de cada producto, el producto de cada precio, stock, especificación o relación, y el depósito de cada fila de stock. La categoría del producto se busca por el par categoría y subcategoría.
- No hay claves repetidas, por ejemplo dos productos con el mismo `product_id` o el mismo `sku`.

Una fila inválida no se carga. El script la informa con la hoja, el número de fila del Excel y el motivo, y sigue con las demás. Si se rechaza un producto, también se rechazan sus precios, su stock y sus especificaciones. Al terminar muestra un resumen por hoja:

```
INFO Loading /data/MercaNova_dataset_obligatorio_2.xlsx
Sheet               Read  Loaded  Rejected
Brands                20      20         0
Categories            37      37         0
Warehouses             5       5         0
Products             360     360         0
Specifications      3000    3000         0
Relations           1080    1080         0
Pricing              360     360         0
Inventory           1800    1800         0
```

Con el Excel actual de la cátedra no se rechaza ninguna fila. Un rechazo se ve así:

```
WARNING Rejected Products row 4: rating: Input should be less than or equal to 5 (got '7.5')
```

**Se puede correr más de una vez.** Cada fila se inserta o, si ya existe, se actualiza (`INSERT ... ON CONFLICT DO UPDATE` sobre la clave de cada tabla). Correrlo dos veces con el mismo archivo deja los mismos datos. Si el Excel cambia, se actualizan las filas que ya estaban. Las filas que se borren del Excel no se borran de la base.

**Todo o nada.** La carga completa corre en una sola transacción. Si algo inesperado falla a mitad de camino, por ejemplo la base rechaza una fila, no queda nada cargado a medias.

El script solo escribe las tablas del catálogo, de precios y de stock. No toca carritos, órdenes, conversaciones ni embeddings.

Las fechas del Excel no tienen zona horaria; se guardan como hora UTC.

## Migraciones

El esquema de la base se versiona con Alembic. Cada cambio de tablas es un archivo en `migrations/versions/`.

```bash
docker compose exec backend alembic upgrade head      # aplicar todas las migraciones
docker compose exec backend alembic downgrade base    # deshacerlas todas (borra las tablas)
docker compose exec backend alembic current           # ver en qué versión está la base
```

Para crear una migración nueva después de cambiar un modelo:

```bash
docker compose exec backend alembic revision --autogenerate -m "describe the change"
```

Alembic compara los modelos con la base y propone el cambio. Hay que revisar el archivo generado antes de aplicarlo.

## Tests

```bash
make test-backend                       # o: docker compose exec backend pytest
docker compose exec backend pytest tests/unit          # solo los que no usan base
docker compose exec backend pytest -m integration      # solo los de base de datos
```

**Cómo se aíslan los tests de la base de desarrollo.** Los tests de integración nunca escriben en la base `mercanova` que usa la aplicación:

1. Al empezar, crean una base aparte, `mercanova_test`, en el mismo servidor de PostgreSQL, y le aplican todas las migraciones.
2. Cada test corre dentro de una transacción que se deshace al terminar. Ningún test ve los datos de otro.
3. Los tests de migraciones usan otra base más, `mercanova_test_migrations`, porque necesitan crear y borrar el esquema completo.
4. Al terminar, las dos bases de test se borran.

Por seguridad, el código se niega a recrear una base con el mismo nombre que la de `DATABASE_URL`.

Qué verifican hoy:

- La migración crea todas las tablas y la extensión `vector` desde una base vacía, se puede deshacer y se puede volver a aplicar.
- El esquema que crea la migración coincide con los modelos de SQLAlchemy.
- La base rechaza datos inválidos: stock disponible negativo, cantidad 0 en el carrito, estado de orden desconocido, retiro sin depósito y asignaciones de stock sin línea de orden.
- `/api/health` informa `db: "ok"` con la base levantada y `db: "down"` cuando no responde.
