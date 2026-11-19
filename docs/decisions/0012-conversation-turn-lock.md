# Decisión 0012: Un turno por vez en cada conversación, con un candado consultivo de PostgreSQL

- **Estado:** propuesta
- **Fecha:** 19/11/2026
- **Autores:** Agustín Vignolo y Florencia Mendoza (Grupo 8, N8B)

## Problema

Cada conversación guarda el estado del asistente (objetivo, productos mostrados, herramientas usadas) en una fila de la base. Un turno lee ese estado al empezar y lo guarda al terminar. Entre una cosa y la otra pasan entre 10 y 50 segundos, porque el modelo local tarda.

Si el cliente manda un segundo mensaje mientras el primero se procesa (doble clic, dos pestañas, reintento), los dos turnos leen el mismo estado y el último en guardar pisa al otro. Se pierden los productos mostrados por uno de los dos, y "el primero" puede apuntar al producto equivocado. Eso rompe la regla de que el estado se mantiene explícito y consistente entre mensajes (decisión 0009).

Hay que decidir cómo se garantiza que los turnos de una misma conversación corran de a uno.

## Alternativas

| Opción | A favor | En contra |
|---|---|---|
| **Candado consultivo de PostgreSQL, en una conexión propia del turno (elegida)** | Dura hasta que se libera o termina la sesión, y no depende de las transacciones: los commits del carrito en medio del turno no lo sueltan [1]. El segundo turno espera en vez de fallar. Si el proceso muere, el servidor limpia el candado al terminar la sesión [1]. No necesita migración. | Ocupa una conexión del pool durante todo el turno. Hay que liberarlo a mano en un `finally`. |
| Candado de fila (`SELECT ... FOR UPDATE` sobre la conversación) | Es lo más conocido y lo que pedía la issue original. | Los candados de fila se sueltan al terminar la transacción [2], y las herramientas del carrito hacen `commit` en medio del turno. El candado desaparecería justo cuando más se necesita. |
| Versión optimista (columna `version` y rechazo si cambió) | No retiene ninguna conexión. | Pide una migración. El turno perdedor ya gastó 30 segundos de modelo y habría que rehacerlo o descartarlo. |
| No hacer nada y deshabilitar el botón de enviar en el frontend | Cero código en el backend. | No protege dos pestañas ni un reintento. La garantía quedaría en el navegador, y el backend no se puede fiar de él. |

## Decisión

- Un método nuevo del repositorio de conversaciones, `turn_lock(conversation_id)`, que se usa en `ChatService.handle` solo cuando el mensaje llega a una conversación existente. Una conversación nueva no tiene con quién competir.
- El candado se toma con `pg_try_advisory_lock` sobre una conexión propia del turno, separada de la sesión de las herramientas. Se reintenta cada 0,1 s durante 30 s como máximo.
- Si pasan los 30 s, se lanza `ConversationBusy`. El endpoint normal responde 409 con el código `CONVERSATION_BUSY` y el stream envía un evento `error` con el mismo código. No se guarda nada.
- El candado se libera siempre en un `finally`, aunque el turno falle.

## Justificación

- **Garantía en el servidor.** El backend es quien decide qué estado vale, no el navegador.
- **Sobrevive a los commits.** Es la propiedad que descarta el candado de fila: la documentación de PostgreSQL dice que los candados de fila se liberan al terminar la transacción [2] y que los consultivos de sesión siguen vigentes hasta que se liberan o termina la sesión, sin importar los commits ni los rollbacks [1].
- **Un test lo comprueba.** Guardar el turno (que hace commit) dentro del candado no lo libera, y otra conversación no queda bloqueada.

## Costos y riesgos (trade-offs)

- **Un turno colgado retiene el candado.** Si el modelo tarda, el segundo mensaje espera hasta 30 s y después recibe el 409. El tiempo máximo de un turno (todavía sin implementar, tarea aparte) acotaría esa espera.
- **Una conexión por turno en curso.** Cada turno retiene una conexión del pool de SQLAlchemy mientras dura, y el pool tiene un tamaño finito. Para este prototipo, con un usuario por vez, no es un riesgo. En producción habría que dimensionar el pool o mover el candado a un servicio aparte.
- **El tope de 30 s es un valor elegido, no medido.** Alcanza para los turnos sin razonamiento (unos 14 s en promedio, decisión 0011). Con el razonamiento activado, que tarda unos 52 s, un segundo mensaje recibiría el 409.
- **Colisiones del identificador.** El candado se calcula con `hashtext` sobre el id de la conversación, que devuelve un entero de 32 bits. Dos conversaciones distintas podrían compartir candado y esperarse sin necesidad. Es raro y solo retrasa, nunca pisa datos.

## Fuentes

1. PostgreSQL 16, *Explicit Locking, Advisory Locks* (un candado consultivo de sesión se mantiene hasta que se libera explícitamente o termina la sesión, y no respeta la semántica de transacciones): https://www.postgresql.org/docs/16/explicit-locking.html#ADVISORY-LOCKS
2. PostgreSQL 16, *Explicit Locking, Row-Level Locks* (los candados de fila se liberan al terminar la transacción o con un rollback a un savepoint): https://www.postgresql.org/docs/16/explicit-locking.html#LOCKING-ROWS
