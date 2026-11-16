# Decisión 0006: Cómo funciona el carrito y cómo valida el stock

- **Estado:** propuesta
- **Fecha:** 15/11/2026
- **Autores:** Agustín Vignolo y Florencia Mendoza (Grupo 8, N8B)

## Problema

La letra pide un carrito donde se pueda agregar, quitar y cambiar cantidades, y que muestre el total (RF-09). También pide que no se pueda comprar más de lo disponible (RF-10).

La decisión 0002 ya fijó que el carrito vive en la base de datos y que no reserva stock. Quedan por resolver cuatro cosas:

1. Qué guarda el carrito y de dónde salen el precio y el stock que se muestran.
2. Cómo se evita que dos pedidos de la misma sesión se pisen.
3. Qué significa "agregar" cuando el producto ya está en el carrito.
4. Qué pasa con un producto que ya no se vende o que no tiene precio.

## Alternativas

**1. Qué guarda el carrito**

| Opción | A favor | En contra |
|---|---|---|
| **Solo producto y cantidad; precio, nombre y stock se leen en cada pedido (elegida)** | El precio que se muestra siempre es el actual (información actual, RF-07). Si el precio cambia, el carrito lo refleja sin migrar nada. | Cada lectura del carrito hace una consulta con varias uniones. |
| Guardar también el precio al agregar | Una consulta más simple. El usuario ve el precio que vio al agregar. | El carrito puede mostrar un precio viejo. Hay que decidir cuándo refrescarlo. La orden ya guarda el precio congelado (decisión 0002), y ahí sí hace falta. |

**2. Pedidos simultáneos de la misma sesión**

| Opción | A favor | En contra |
|---|---|---|
| **Bloquear la fila del carrito con `SELECT ... FOR UPDATE` mientras se escribe (elegida)** | Dos pedidos de una misma sesión (por ejemplo, dos clics rápidos) se ejecutan uno después del otro. La suma de cantidades y la verificación de stock no se pisan [1]. La fila del carrito se crea con `INSERT ... ON CONFLICT DO NOTHING`, así que dos primeros pedidos no chocan [2]. | El bloqueo dura lo que dura la escritura. Es corto. |
| Control optimista: un número de versión que se compara al guardar | No bloquea. | Hay que reintentar y exponer el conflicto al frontend. Más código para un caso poco frecuente. |
| No proteger | Cero código. | Dos clics rápidos pueden dejar una cantidad incorrecta. |

**3. Qué hace "agregar" si el producto ya está**

| Opción | A favor | En contra |
|---|---|---|
| **Suma a la cantidad que ya había (elegida)** | Es lo que dice el contrato de la API. El límite de stock se compara contra el total resultante, así no se puede superar el stock agregando de a poco. | El frontend tiene que usar el cambio de cantidad para fijar un valor exacto. |
| Reemplaza la cantidad | Más simple. | Contradice el contrato. Agregar dos veces dejaría una sola unidad. |

**4. Producto inactivo o sin precio**

| Opción | A favor | En contra |
|---|---|---|
| **Se rechaza con `PRODUCT_INACTIVE` (elegida)** | Un producto sin precio no se puede comprar, y mostrarle al usuario un error de "no disponible" es lo más honesto. Es el mismo código que ya define el contrato. | "Sin precio" e "inactivo" comparten código, aunque son causas distintas. Hoy los 360 productos tienen precio. |
| Un código de error nuevo para "sin precio" | Más preciso. | El contrato de la API cambiaría. Es un cambio que van a revisar las dos personas, y hoy no ocurre con el dataset. |

## Decisión

- **El carrito guarda producto y cantidad.** Nombre, imagen, precio, subtotal y stock disponible se leen de la base en cada pedido. El total se calcula al mostrar.
- **Agregar suma y valida contra el total.** Si la cantidad que quedaría en el carrito supera el stock disponible, se responde `INSUFFICIENT_STOCK` con `available_qty`, y el carrito no cambia. Ejemplo del caso de uso 6: pedir 50 unidades con 9 disponibles.
- **Cambiar la cantidad fija el valor.** Mínimo 1 y máximo 1000 por producto. Un producto que no está en el carrito da `PRODUCT_NOT_FOUND` con el mensaje "El producto no está en el carrito".
- **Quitar es idempotente.** Quitar algo que no está devuelve el carrito sin cambios.
- **Sesión.** El encabezado `X-Session-Id` es obligatorio (`MISSING_SESSION`) y no puede tener más de 64 caracteres. Cada sesión ve solo su carrito.
- **Producto inactivo o sin precio.** `PRODUCT_INACTIVE`. Hoy no hay productos sin precio en el dataset.
- **El carrito no toca el stock.** Un test comprueba que el inventario no cambia con ninguna operación del carrito.
- **Los errores salen en un solo lugar.** Las excepciones del dominio se convierten en el cuerpo de error del contrato en el manejador de errores común (decisión 0003).

## Justificación

- **Precio y stock actuales (RF-07 y RF-10).** Al leerlos en cada pedido, el carrito nunca muestra un valor viejo. Un test cambia el precio y el stock con SQL directo entre dos lecturas y comprueba que aparecen los valores nuevos.
- **No superar lo disponible (RF-10).** Se compara el total del carrito, no solo lo que se agrega ahora. En la prueba contra la base real, agregar 2 y luego pedir 50 con 9 disponibles dio `INSUFFICIENT_STOCK` y el carrito siguió con 2.
- **Sin ventas dobles.** Que el carrito no reserve stock evita carritos abandonados que bloqueen unidades. La garantía fuerte está en la confirmación de la compra, que vuelve a validar todo dentro de una transacción.

## Costos y riesgos (trade-offs)

- **El stock puede cambiar después de agregar.** Como no hay reserva, un producto puede agotarse entre que se agrega y se compra. El aviso llega al confirmar.
- **La verificación de stock al agregar lee el stock antes de tomar el bloqueo.** Otra sesión puede comprar en ese instante. No importa para la corrección final, porque la confirmación revalida con bloqueo de filas, pero el carrito puede aceptar una cantidad que un instante después deja de estar disponible.
- **Un producto que pierde su fila de precio desaparece del carrito.** La lectura del carrito usa una unión interna con precios. Es coherente con que un producto sin precio no se puede comprar, pero el usuario no recibe un aviso. Con el dataset actual no ocurre.
- **Un solo código para "inactivo" y "sin precio".** Si el contrato necesita distinguirlos, es un cambio aparte.
- **No hay test de concurrencia del carrito.** El bloqueo de la fila se ejercita con pedidos secuenciales. El test de dos compras simultáneas está en la confirmación de la compra, que es donde importa.

## Fuentes

1. PostgreSQL 16, *Explicit Locking* (bloqueo de filas con `SELECT ... FOR UPDATE`): https://www.postgresql.org/docs/16/explicit-locking.html
2. PostgreSQL 16, *INSERT* (cláusula `ON CONFLICT`): https://www.postgresql.org/docs/16/sql-insert.html
3. FastAPI, *Header Parameters* (lectura del encabezado `X-Session-Id`): https://fastapi.tiangolo.com/tutorial/header-params/
4. Decisiones 0002 (carrito en la base de datos, stock sin reserva) y 0003 (manejo de errores).
