# Decisión 0001: Tecnologías de la solución

- **Estado:** aceptada
- **Fecha:** 12/11/2026
- **Autores:** Agustín Vignolo y Florencia Mendoza (Grupo 8, N8B)

## Problema

Hay que construir en unas cuatro semanas, y entre dos personas, un e-commerce con asistente de IA. Tiene que incluir frontend, backend, base de datos, un modelo de lenguaje que use herramientas, búsqueda semántica y entrada por voz. La letra pide además que todo se pueda levantar en una computadora local con Docker y que las credenciales vayan en variables de entorno.

Elegimos cada pieza con tres criterios:

1. **Que resuelva lo que pide la letra:** asistente que no invente datos, voz, compra con stock real y ejecución local.
2. **Que sea fácil de explicar y defender:** cada componente con una responsabilidad clara.
3. **Que el equipo lo pueda construir a tiempo.**

## Resumen de la decisión

| Pieza | Elegimos | Alternativas evaluadas |
|---|---|---|
| Modelo de lenguaje | **Ollama** corriendo modelos abiertos en local | API de OpenAI o Anthropic, LM Studio, vLLM |
| Base de datos | **PostgreSQL con la extensión pgvector** | PostgreSQL + base vectorial aparte (Chroma, Qdrant), SQLite + FAISS |
| Backend | **Python con FastAPI** | Node.js con Express, .NET |
| Frontend | **React con Vite y TypeScript** | Next.js, Streamlit |
| Voz a texto | **faster-whisper** en local | Web Speech API del navegador, servicio de voz en la nube |
| Ejecución | **Docker Compose** | Instalación manual |

---

## 1. Modelo de lenguaje: Ollama

**Qué necesitamos:** un modelo que entienda español, que pueda **llamar herramientas** (buscar productos, consultar precio y stock, armar el carrito) y que corra sin costo durante el desarrollo y la corrección.

| Opción | A favor | En contra |
|---|---|---|
| **Ollama (elegida)** | Corre en local y gratis. Tiene una API simple, soporta *tool calling* y permite cambiar de modelo con una variable de entorno. Lo recomienda la cátedra. | Los modelos locales son más lentos y menos precisos que los comerciales. Necesita unos 8 GB de RAM. |
| API de OpenAI / Anthropic | Los modelos más precisos para usar herramientas. Sin requisitos de hardware. | Costo por uso, requiere una clave de API. Si el docente no tiene clave, no puede ejecutar la solución. |
| LM Studio | Interfaz gráfica cómoda para probar modelos. | Pensado para uso de escritorio, no para correr dentro de Docker. |
| vLLM | Muy rápido en servidores con GPU. | Requiere GPU NVIDIA. Es excesivo para un prototipo local. |

**Por qué Ollama:** es la única opción que cumple a la vez "se ejecuta en local con Docker", "sin secretos obligatorios" y "con herramientas". La documentación oficial confirma que soporta *tool calling*: el modelo pide ejecutar una función y la aplicación le devuelve el resultado [1]. El backend accede al modelo a través de una interfaz propia, así que pasar a un proveedor comercial es cambiar una variable de entorno, sin tocar la lógica.

**Qué modelos vamos a comparar:** solo sirven los modelos que Ollama marca con la capacidad *tools* [2]. Preseleccionamos tres que entran en una notebook:

| Modelo | Tamaño | Por qué está en la comparación |
|---|---|---|
| `qwen3:8b` | 8 mil millones de parámetros | Soporta herramientas y razonamiento [3]. La familia Qwen aparece entre las mejores abiertas en el Berkeley Function Calling Leaderboard [4]. |
| `llama3.1:8b` | 8 mil millones | El modelo con herramientas más descargado de Ollama (más de 120 millones de descargas) [5]. Sirve de referencia. |
| `qwen3:4b` | 4 mil millones | Versión más liviana, para medir cuánto se pierde en calidad a cambio de velocidad. |

El *Berkeley Function Calling Leaderboard* es el benchmark público de referencia para medir qué tan bien un modelo elige y completa llamadas a funciones [4]. Como los rankings cambian con cada versión, no elegimos el modelo final por el ranking: lo elegimos **probando los tres con nuestros 10 casos de uso** (tarea AI-07). Medimos si elige la herramienta correcta, si pide aclaración cuando falta información, si inventa datos y cuánto tarda.

**Modelo de embeddings:** `nomic-embed-text`. Pesa 274 MB y corre en Ollama, así que no suma otro servicio. Según su ficha supera a los modelos de embeddings de OpenAI `ada-002` y `text-embedding-3-small` [6]. Ese dato lo informa el propio autor, no es una medición independiente.

## 2. Base de datos: PostgreSQL con pgvector

**Qué necesitamos:** guardar productos, precios, stock, carritos y órdenes con **transacciones**, para que dos compras no vendan la misma unidad. También necesitamos **búsqueda por similitud de significado** sobre las descripciones (RAG).

| Opción | A favor | En contra |
|---|---|---|
| **PostgreSQL + pgvector (elegida)** | Una sola base para los datos y los vectores. En una misma consulta se combina "parecido a lo que pidió" con "precio menor a USD 200 y con stock". Transacciones reales. | Para millones de vectores rinde menos que una base dedicada. |
| PostgreSQL + Chroma o Qdrant | Bases diseñadas solo para vectores, muy rápidas a gran escala. | Dos sistemas que hay que mantener sincronizados. Los filtros por precio y stock quedarían en otra base. |
| SQLite + FAISS | Muy simple, sin servidor. | Sin bloqueo de filas para el stock concurrente. FAISS es una librería, no persiste solo. |

**Por qué pgvector:** el catálogo tiene 360 productos, muy lejos de la escala donde una base vectorial dedicada empieza a convenir [7][8]. La ventaja que más nos importa es filtrar y unir datos en la misma consulta. Con una base aparte habría que sincronizar dos sistemas [8].

## 3. Backend: Python con FastAPI

| Opción | A favor | En contra |
|---|---|---|
| **FastAPI (elegida)** | Valida los datos con modelos tipados (Pydantic) y genera la documentación de la API automáticamente [9]. Las librerías de IA (cliente de Ollama, Whisper) están primero en Python. | El frontend queda en otro lenguaje (TypeScript). |
| Node.js con Express | Un solo lenguaje en todo el proyecto. | Faster-whisper y gran parte del ecosistema de IA están en Python. Habría que sumar un servicio extra. |
| .NET | Robusto y tipado. | El equipo lo conoce menos y el ecosistema de IA local es menor. |

**Por qué FastAPI:** los mismos modelos tipados describen las herramientas que usa el LLM, validan las respuestas estructuradas y documentan la API. Escribimos cada estructura una sola vez.

El backend se organiza en capas: dominio, casos de uso y adaptadores. Las reglas de negocio (carrito, stock, órdenes) no dependen de la base ni del modelo de lenguaje, así que se pueden probar sin levantar ninguno de los dos.

## 4. Frontend: React con Vite y TypeScript

| Opción | A favor | En contra |
|---|---|---|
| **React + Vite (elegida)** | Una aplicación web real, con componentes reutilizables y arranque rápido en desarrollo [10]. TypeScript detecta errores de contrato con la API. | Hay que armar el ruteo y el manejo de estado. |
| Next.js | Incluye ruteo y renderizado en servidor. | Agrega complejidad que un prototipo local no necesita. |
| Streamlit | Muy rápido para prototipos de datos. | Parece una herramienta de análisis, no una tienda. La letra pide que "no sea una prueba de consola o un notebook". |

Los colores, tamaños y tipografías se definen en un solo archivo de *design tokens*. Los componentes visuales no piden datos: los reciben. Así se puede cambiar el estilo o reutilizar componentes sin tocar la lógica.

## 5. Voz a texto: faster-whisper

| Opción | A favor | En contra |
|---|---|---|
| **faster-whisper (elegida)** | Mismo modelo Whisper de OpenAI, hasta 4 veces más rápido y con menos memoria [11]. Corre en local y entiende español. | Agrega unos segundos de procesamiento en CPU. |
| Web Speech API del navegador | No requiere backend. | Funciona distinto según el navegador, y en Chrome envía el audio a servidores externos. |
| Servicio en la nube | Muy preciso y rápido. | Costo y clave de API, el mismo problema que con el LLM. |

## 6. Ejecución: Docker Compose

La letra pide que un docente pueda clonar el repositorio y levantar la solución siguiendo la documentación. Con Docker Compose, un solo comando (`docker compose up`) levanta la base, Ollama, el backend y el frontend, con las mismas versiones en cualquier máquina.

---

## Costos y riesgos que aceptamos

- **Calidad del modelo local:** es menor que la de un modelo comercial. Lo mitigamos con herramientas bien tipadas, reglas en el prompt, validaciones en el backend (por ejemplo, ningún precio se muestra si no salió de la base en ese turno) y la comparación de modelos.
- **Hardware:** Ollama y Whisper necesitan unos 8 GB de RAM. Queda indicado en el README.
- **Dos lenguajes en el repositorio:** Python y TypeScript. Cada carpeta tiene reglas claras y una *skill* para el coding agent.
- **Escala:** pgvector y un único backend alcanzan para el prototipo. En producción habría que evaluar una base vectorial dedicada y múltiples instancias del backend.

## Fuentes

1. Ollama, *Tool calling*: https://docs.ollama.com/capabilities/tool-calling
2. Ollama, modelos con capacidad *tools*: https://ollama.com/search?c=tools
3. Ollama, ficha de `qwen3`: https://ollama.com/library/qwen3
4. UC Berkeley, *Berkeley Function Calling Leaderboard* (V4, actualizado el 12/04/2026): https://gorilla.cs.berkeley.edu/leaderboard.html
5. Ollama, ficha de `llama3.1`: https://ollama.com/library/llama3.1
6. Ollama, ficha de `nomic-embed-text`: https://ollama.com/library/nomic-embed-text
7. pgvector (repositorio oficial): https://github.com/pgvector/pgvector
8. ClickHouse, *How to scale vector search in Postgres (pgvector)*: https://clickhouse.com/resources/engineering/scale-vector-search-postgres
9. FastAPI, documentación oficial: https://fastapi.tiangolo.com/
10. Vite, documentación oficial: https://vite.dev/guide/
11. SYSTRAN, faster-whisper (repositorio oficial): https://github.com/SYSTRAN/faster-whisper
