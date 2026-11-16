# Decisión 0007: Cómo se crea y se confirma una compra

- **Estado:** propuesta
- **Fecha:** 15/11/2026
- **Autores:** Agustín Vignolo y Florencia Mendoza (Grupo 8, N8B)

## Problema

La letra pide completar una compra ficticia de punta a punta. Tiene que haber un paso de checkout con los datos mínimos (RF-11), una confirmación explícita antes de registrar nada (RF-12), un número de orden propio (RF-14) y el descuento de stock de lo vendido (RF-15).

La decisión 0002 ya fijó que el stock se descuenta al confirmar, dentro de una transacción con bloqueo de filas, y que la orden guarda el precio de cada línea. El contrato de la API define dos pasos: crear una orden pendiente y confirmarla. Quedan por resolver cuatro cosas:

1. Cómo se evita vender dos veces la última unidad cuando dos personas confirman a la vez.
2. Cómo se evitan los bloqueos mutuos (*deadlocks*) entre confirmaciones simultáneas.
3. De qué depósito sale cada unidad.
4. Cómo se genera el número de orden sin repetirlo.

## Alternativas

**1. Evitar la venta doble del último producto**

| Opción | A favor | En contra |
|---|---|---|
| **Bloquear las filas de inventario con `SELECT ... FOR UPDATE` y revalidar adentro de la transacción (elegida)** | Quien llega segundo espera, ve el stock ya descontado y recibe `INSUFFICIENT_STOCK`. Es la herramienta que PostgreSQL ofrece para esto [1]. | Las confirmaciones de un mismo producto se ejecutan una por una. Para un prototipo no importa. |
| Descontar con `UPDATE ... WHERE available_qty >= n` y mirar cuántas filas cambiaron | No toma bloqueos explícitos. | Hay que armar la lógica de varios depósitos y precios alrededor de una condición en el `UPDATE`. Es más difícil de leer y de probar. |
| Reservar stock al crear la orden pendiente | La unidad queda asegurada mientras el usuario decide. | Las órdenes pendientes no vencen (contrato), así que bloquearían stock para siempre. Ya se descartó en la decisión 0002. |

**2. Bloqueos mutuos entre confirmaciones**

| Opción | A favor | En contra |
|---|---|---|
| **Tomar siempre los bloqueos en el mismo orden (elegida)** | Es la defensa que recomienda la documentación de PostgreSQL: que todas las transacciones tomen los bloqueos en un orden consistente [2]. Primero la fila de la orden y después las filas de inventario ordenadas por producto y depósito. | Hay que respetar el orden en todo código que bloquee inventario. |
| Dejar que PostgreSQL detecte el deadlock y reintentar | No exige orden. | Una de las compras falla al azar y hay que reintentarla [2]. |

**3. De qué depósito sale cada unidad**

| Opción | A favor | En contra |
|---|---|---|
| **Retiro: del depósito elegido. Envío: del depósito con más unidades, y si no alcanza, del siguiente (elegida)** | Es lo que define el contrato. Con envío se minimiza la cantidad de depósitos involucrados. La tabla de asignaciones deja registrado de dónde salió cada unidad (decisión 0002). | No optimiza por cercanía al cliente: el dataset no trae distancias. |
| Siempre del depósito con más stock | Más simple. | Para un retiro, sacaría la unidad de un depósito distinto al que eligió el usuario. |

**4. Número de orden**

| Opción | A favor | En contra |
|---|---|---|
| **`ORD-AAAAMMDD-NNNN`, con un contador diario protegido por un bloqueo de PostgreSQL (elegida)** | Es el formato del contrato y se puede leer a simple vista. El bloqueo de aviso (*advisory lock*) hace que dos órdenes creadas a la vez no tomen el mismo número [3]. No requiere una tabla ni una migración nueva. | El contador depende de la fecha en UTC. |
| Un identificador aleatorio (UUID) | No hay riesgo de repetirse. | No es legible. El contrato muestra el formato con fecha. |
| Una secuencia de PostgreSQL | Es el mecanismo estándar para números únicos. | Necesita una migración y no se reinicia por día. |

## Decisión

- **Checkout (paso 1).** `POST /api/checkout` lee el carrito de la sesión con los precios actuales, verifica el stock **sin bloquear ni descontar**, y crea la orden `pending_confirmation` con el nombre y el precio de cada línea copiados. El carrito no se vacía. Errores: `CART_EMPTY`, `INSUFFICIENT_STOCK` y `PRODUCT_INACTIVE`.
- **Regla de stock.** Con retiro se compara contra el depósito elegido. Con envío, contra la suma de los depósitos que permiten envío.
- **Datos del cliente.** Nombre, email y dirección son obligatorios. El email se valida con un patrón simple, sin una dependencia nueva. Una respuesta de error indica el campo y el problema, nunca el valor enviado.
- **Confirmación (paso 2).** `POST /api/orders/{id}/confirm` corre en una sola transacción:
  1. Bloquea la fila de la orden. Debe ser de la sesión y estar pendiente, o responde `ORDER_NOT_FOUND` u `ORDER_NOT_PENDING`.
  2. Bloquea las filas de inventario de sus productos, ordenadas por producto y depósito.
  3. Una función pura del dominio decide: primero revalida el stock (`INSUFFICIENT_STOCK`), después el precio (`PRICE_CHANGED`, con el precio viejo y el nuevo) y arma el plan de asignación entre depósitos.
  4. Aplica el plan: descuenta `on_hand_qty` y `available_qty` juntos (así `available = on_hand - reserved` sigue valiendo), registra las asignaciones, marca la orden como confirmada y vacía el carrito.
  5. Si algo falla en cualquier punto, se deshace todo.
- **Cancelar.** Solo una orden pendiente se puede cancelar. No toca el stock, porque una orden pendiente no lo reserva.
- **Quién puede confirmar.** Únicamente el usuario, con el botón de la interfaz. No existe ninguna herramienta del asistente para confirmar o cancelar (decisión 0005).
- **Número de orden.** Se genera dentro de la misma transacción que inserta la orden.

## Justificación

- **Confirmación explícita (RF-12).** Nada se compra en el checkout: la orden pendiente es un borrador sin efectos. El stock solo cambia en el paso 2, que el usuario dispara con un clic.
- **Sin ventas dobles (RF-15).** Hay un test con dos hilos reales que confirman a la vez la última unidad: exactamente uno tiene éxito, el otro recibe `INSUFFICIENT_STOCK` y el stock queda en 0, nunca negativo. Otro test confirma la misma orden desde dos hilos: una sola tiene éxito y el stock se descuenta una vez. Las dos pruebas se repitieron 8 veces seguidas sin fallar.
- **Las pruebas detectan la falta de bloqueo.** Se quitó a propósito el bloqueo del inventario y el test de la última unidad falló en 4 de 6 corridas. Se quitó el bloqueo de la orden y el test de la misma orden falló en 6 de 6. La ventana de la carrera es corta, por eso el primero no falla siempre: el test lo detecta, pero no en cada corrida.
- **Todo o nada.** Un test arma una orden con dos productos donde al segundo no le alcanza el stock y comprueba que el stock del primero no se descontó.
- **Historial fiel (decisión 0002).** El precio que se compara al confirmar es el copiado en la orden. Si cambió, el usuario recibe `PRICE_CHANGED` y la orden sigue pendiente.
- **Datos personales.** El nombre, el email y la dirección no se registran en ningún log. Un test fuerza un error inesperado y comprueba que no aparecen en el registro.
- **Prueba real.** Contra la base cargada: se agregaron 3 unidades de un producto con 9, el checkout no cambió el stock, la confirmación lo bajó a 6 en el depósito elegido y registró la asignación. Confirmar de nuevo dio `ORDER_NOT_PENDING`. Con un precio modificado en la base, la confirmación dio `PRICE_CHANGED` y la orden siguió pendiente. Después se restauró la base.

## Costos y riesgos (trade-offs)

- **El stock se valida dos veces.** Al crear la orden y al confirmarla. Es intencional: entre un paso y otro puede cambiar. A cambio, el usuario a veces recibe un error en el paso 2 que no tuvo en el paso 1.
- **Las órdenes pendientes no vencen.** Pueden acumularse. No reservan stock, así que no afectan las ventas. En producción se limpiarían con una tarea periódica (contrato de la API).
- **Un precio que cambió obliga a rehacer la orden.** El usuario tiene que volver a armarla. Es lo que pide el contrato y evita cobrar un precio que el usuario no vio.
- **La asignación de envío no optimiza por distancia.** Toma el depósito con más stock. El dataset no trae distancias.
- **Las líneas de la orden se devuelven ordenadas por identificador de producto**, no por el orden en que se agregaron al carrito, porque la tabla de líneas no guarda ese orden.
- **Un producto sin precio o inactivo al confirmar da `PRODUCT_INACTIVE`**, igual que en el carrito (decisión 0006). Con el dataset actual no ocurre.
- **Si la confirmación se cae justo después de commitear, el cliente puede no enterarse.** Pedir de nuevo la confirmación responde `ORDER_NOT_PENDING`, y el historial de la sesión muestra la orden confirmada.
- **El número de orden usa la fecha en UTC.** Una compra hecha a la noche en Uruguay puede llevar la fecha del día siguiente.
- **Los tests de concurrencia insertan datos reales en la base de pruebas** y los borran al terminar. Si el proceso se corta a la mitad, quedan filas con prefijo `CC-` hasta la próxima corrida.

## Fuentes

1. PostgreSQL 16, *Explicit Locking* (bloqueo de filas con `SELECT ... FOR UPDATE`): https://www.postgresql.org/docs/16/explicit-locking.html
2. PostgreSQL, *Explicit Locking*, sección 13.3.4 *Deadlocks* ("la mejor defensa es que todas las aplicaciones tomen los bloqueos sobre varios objetos en un orden consistente"): https://www.postgresql.org/docs/current/explicit-locking.html
3. PostgreSQL 16, *Advisory Locks* (`pg_advisory_xact_lock`, bloqueo que se libera al terminar la transacción): https://www.postgresql.org/docs/16/explicit-locking.html#ADVISORY-LOCKS
4. Decisiones 0002 (stock sin reserva y precio copiado en la orden), 0005 (el asistente no tiene herramientas para confirmar) y 0006 (carrito).
