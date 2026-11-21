# MercaNova: asistente de compras con inteligencia artificial

**Universidad ORT Uruguay**
**Sistemas de Soporte de Decisión: Obligatorio 2**

| | |
|---|---|
| Grupo | 8 (N8B) |
| Integrantes | Agustín Vignolo (n.º de estudiante 264272) · Florencia Mendoza (n.º de estudiante 285422) |
| Docentes | Santiago Díaz y Carlos Nieves |
| Fecha de entrega | 07/12/2026 |
| Repositorio | https://github.com/Saikus08/mercanova-ai-assistant |

---

## Resumen ejecutivo

**Qué es.** MercaNova es un prototipo de tienda online para una empresa ficticia de tecnología, con un asistente de compras basado en inteligencia artificial. El usuario le cuenta al asistente lo que necesita, por escrito o por voz, en lenguaje natural ("Necesito unos auriculares cómodos para trabajar y hacer videollamadas. No quiero gastar más de USD 200."). El asistente busca en el catálogo, recomienda productos explicando por qué, compara opciones, pide más datos si el pedido es ambiguo y ayuda a armar el carrito. La compra es ficticia: no hay pagos ni tarjetas.

**Cómo funciona.**
- **Un solo agente con herramientas.** El modelo de lenguaje propone qué herramienta usar (buscar productos, consultar precio o stock, comparar, agregar al carrito, preparar la compra). El software valida cada pedido antes de ejecutarlo y controla la respuesta antes de mostrarla.
- **Dos fuentes de información, separadas a propósito.** La información fija del producto (descripción, características, para quién se recomienda) se busca por significado, con vectores guardados en PostgreSQL con pgvector. El precio y el stock, que cambian, se leen siempre de la base de datos en el mismo turno, mediante una herramienta. Nunca salen de la memoria del modelo ni de una copia guardada.
- **Nada se compra sin el usuario.** El asistente solo prepara la compra. La orden se registra cuando el usuario completa sus datos y hace clic en "Confirmar compra". Esa confirmación no es una herramienta del asistente: la hace solo la interfaz. Los datos personales del checkout nunca pasan por el modelo.
- **Todo corre en una computadora local con Docker Compose.** Frontend en React, backend en FastAPI, base PostgreSQL, modelo de lenguaje `qwen3:8b` en Ollama y voz a texto con faster-whisper. No se usa ningún servicio pago ni externo.

**Resultados.**
- Los 18 requerimientos funcionales y los 7 no funcionales de la letra están implementados. Falta una prueba: levantar el proyecto desde un clon limpio siguiendo solo el README. El detalle y dónde comprobar cada uno está en la tabla siguiente.
- El asistente se evaluó con 20 casos fijos (casos de uso, pedidos ambiguos, intentos de manipulación, pedidos fuera de la tienda y casos borde), 3 corridas por caso. Se compararon dos modelos locales. `qwen3:8b` con el razonamiento apagado fue el elegido: cumplió el resultado esperado en el 85 % de las condiciones y usó la herramienta correcta en el 92,5 %. En el 100 % de las respuestas, los montos y los ids de producto salieron de una herramienta o de lo que escribió el usuario. Tardó 14 segundos por turno en promedio en una Apple M1 Max.
- El proyecto tiene tests automáticos del dominio, de la API con la base de datos, del agente con un modelo simulado y de los flujos críticos del frontend. Corren en cada pull request con GitHub Actions.

**Principales limitaciones.**
- Con el modelo local, cada respuesta del asistente tarda varios segundos, y en una computadora sin una GPU con memoria suficiente puede tardar más de un minuto.
- Un modelo de 8 mil millones de parámetros a veces no sigue todas las instrucciones. Por eso las reglas críticas (no inventar precios, no comprar sin confirmación) las controla el software y no el modelo.
- No hay usuarios ni inicio de sesión. Cada navegador tiene su propio carrito, y el asistente no recuerda conversaciones anteriores.

---

## Requerimientos implementados

Estado al 20/11/2026, sobre la rama principal del repositorio. "Dónde verlo" indica la pantalla o el endpoint, y "Comprobado por" indica el test automático o la prueba que lo verifica.

### Requerimientos funcionales

| Código | Requerimiento | Estado | Dónde verlo | Comprobado por |
|---|---|---|---|---|
| RF-01 | **Catálogo de productos:** consultar y ver los productos del dataset | Implementado | Pantalla "Catálogo" (`/`), con búsqueda por texto, filtros por categoría, subcategoría, rango de precio y "Solo con stock", y orden por precio o calificación. Detalle de cada producto con especificaciones y stock por depósito | Tests de la API de catálogo y de las pantallas de catálogo y detalle |
| RF-02 | **Búsqueda y descubrimiento:** encontrar productos a partir de necesidades en lenguaje natural | Implementado | Chat del asistente (`/chat`). La búsqueda compara el significado del pedido con la descripción de cada producto (vectores de `nomic-embed-text` en pgvector) | Tests de la búsqueda semántica con la base de datos y caso de uso 1 de la evaluación |
| RF-03 | **Asistente inteligente:** conversación que entiende pedidos y ayuda durante la compra | Implementado | Chat del asistente, con respuesta en vivo y el panel "Cómo lo resolví", que muestra las herramientas usadas | Tests del ciclo del agente con un modelo simulado y evaluación con 20 casos contra el modelo real |
| RF-04 | **Recomendaciones:** recomendar alternativas y explicar por qué | Implementado | Tarjetas de producto en el chat, cada una con el motivo de la recomendación y el botón "Agregar al carrito" | Tests del ciclo del agente y caso de uso 1 de la evaluación |
| RF-05 | **Aclaraciones:** pedir más información cuando el pedido es ambiguo | Implementado | Ante "Quiero un monitor", el chat pregunta para qué y cuánto quiere gastar, con botones de respuesta rápida | Tests del ciclo del agente (búsqueda vaga bloqueada) y caso de uso 2 de la evaluación |
| RF-06 | **Comparación:** comparar alternativas con información del sistema | Implementado | Tabla comparativa en el chat ("Compará el primero con el segundo") y endpoint `GET /api/products/compare` | Tests de la API de comparación y caso de uso 3 de la evaluación |
| RF-07 | **Información actual:** precio y disponibilidad siempre leídos del estado actual | Implementado | Las herramientas `get_price` y `get_stock` leen la base en cada llamada. Las tarjetas del chat se arman con los datos de esa misma lectura | Tests del ciclo del agente: un precio que no salió de una herramienta del turno provoca un reintento y, si sigue, una respuesta degradada |
| RF-08 | **Entrada por voz:** consultar por voz, convirtiendo el audio a texto | Implementado | Botón de micrófono en el chat (Chrome). El audio se transcribe en el backend con faster-whisper (modelo `small`, en español) y se envía como un mensaje más | Tests del endpoint de transcripción y del botón de voz. Prueba manual con micrófono en Chrome el 19/11/2026 |
| RF-09 | **Carrito:** agregar, quitar, cambiar cantidades y ver el total | Implementado | Pantalla "Carrito" (`/cart`) y botones "Agregar al carrito" del catálogo, el detalle y el chat. El total lo calcula el servidor | Tests del dominio del carrito, de la API y de las pantallas |
| RF-10 | **Validación de disponibilidad:** no permitir comprar más de lo disponible | Implementado | Agregar más de lo disponible muestra "Solo hay N unidades disponibles." y el carrito no cambia. El checkout y la confirmación vuelven a revisar el stock | Tests de la API del carrito y del checkout, y caso de uso 6 |
| RF-11 | **Checkout:** flujo con los datos mínimos para simular una compra | Implementado | Pantalla "Finalizar compra" (`/checkout`): nombre, email, dirección y forma de entrega (retiro en un depósito o envío) | Tests de la API de checkout y del formulario |
| RF-12 | **Confirmación de compra:** pedir confirmación explícita antes de registrar la compra | Implementado | Diálogo "Confirmá tu compra" con el resumen de la orden. Solo el botón "Confirmar compra" la registra. Desde el chat ("Comprámelo"), el asistente solo prepara la compra y lleva a la misma pantalla | Tests del checkout y del recorrido chat → compra: ninguna orden se confirma sin el clic |
| RF-13 | **Compra ficticia:** completar una compra simulada, sin pagos ni tarjetas reales | Implementado | No se piden ni se guardan datos de tarjeta | Tests de la API de checkout |
| RF-14 | **Orden:** generar un identificador de orden y registrar la operación | Implementado | Al confirmar se muestra el número de orden (por ejemplo `ORD-20261112-0001`). La orden guarda el precio de cada línea al momento de la compra | Tests de la API de órdenes |
| RF-15 | **Actualización de estado:** la compra descuenta el stock | Implementado | Confirmar descuenta el stock en una sola transacción con bloqueo de filas, así dos compras simultáneas no pueden dejar stock negativo | Tests de integración del checkout, incluida la confirmación concurrente |
| RF-16 | **Historial:** consultar las órdenes realizadas | Implementado | Pantalla "Mis compras" (`/orders`) y detalle de cada orden | Tests de la API y de las pantallas de historial |
| RF-17 | **Casos límite:** manejar errores, productos inexistentes, sin stock y consultas ambiguas | Implementado | Producto inexistente, sin stock, consulta ambigua, modelo apagado y audio vacío muestran un mensaje claro en español | Tests por caso en backend y frontend |
| RF-18 | **No invención de información:** no presentar datos que no estén en el sistema | Implementado | Si una búsqueda no encuentra nada, el chat dice que no está en el catálogo. El software descarta tarjetas con ids que ninguna herramienta devolvió y montos que ninguna herramienta devolvió | Tests del ciclo del agente y caso de uso 5 ("¿Cuánto sale una PlayStation 9?") |

### Requerimientos no funcionales

| Código | Requerimiento | Estado | Dónde verlo | Comprobado por |
|---|---|---|---|---|
| RNF-01 | **Ejecución local:** la solución corre completa en una computadora local | Implementado | El modelo de lenguaje (Ollama), los embeddings y la voz a texto corren en la misma máquina. No se usan servicios externos | Uso del proyecto en las computadoras de los dos integrantes (una Mac con Apple M1 Max y una notebook Windows con una RTX 3050) |
| RNF-02 | **Docker:** la aplicación se levanta con Docker Compose | Implementado | `docker-compose.yml` levanta la base, Ollama, el backend y el frontend. El README lista los comandos | Uso del proyecto con Docker Compose en las computadoras de los dos integrantes |
| RNF-03 | **Configuración:** credenciales y configuración en variables de entorno, sin secretos en el repositorio | Implementado | `.env.example` documenta cada variable y `.env` está excluido del repositorio (`.gitignore`) | Un control automático (hook) impide que el coding agent escriba archivos de secretos, y cada pull request se revisa antes de mergearse |
| RNF-04 | **Robustez:** los errores previsibles no pueden colgar la aplicación | Implementado | Cada llamada al modelo tiene un tiempo máximo, y cada turno del asistente un máximo de pasos y de tiempo. Si el modelo no responde, el chat lo informa y el resto de la tienda sigue funcionando | Tests del ciclo del agente (modelo caído, tiempo agotado, pasos agotados) y caso de uso 9 |
| RNF-05 | **Testing:** estrategia de tests que cubra los componentes críticos | Implementado | Tests unitarios del dominio, de integración de la API con PostgreSQL, del agente con un modelo simulado y de los flujos del frontend. Evaluación del asistente con 20 casos contra el modelo real | GitHub Actions corre lint, chequeo de tipos y tests en cada pull request |
| RNF-06 | **Mantenibilidad:** código legible, organizado y coherente con las decisiones documentadas | Implementado | Backend con arquitectura hexagonal (el dominio no depende de frameworks), frontend con design tokens y componentes separados de los que cargan datos, y decisiones de diseño documentadas en `docs/decisions/` | Lint (ruff y oxlint) en el CI y revisión cruzada de cada pull request |
| RNF-07 | **Reproducibilidad:** un docente clona el repositorio y lo levanta siguiendo la documentación | Implementado; prueba pendiente | README con los pasos para levantarlo, cargar el catálogo y probarlo | Falta la prueba desde un clon limpio, siguiendo solo el README, hecha por quien no programó el backend. Está planificada antes de la entrega |
