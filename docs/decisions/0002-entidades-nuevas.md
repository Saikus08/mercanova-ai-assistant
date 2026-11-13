# Decisión 0002: Entidades nuevas para carrito, órdenes y conversación

- **Estado:** propuesta
- **Fecha:** 12/11/2026
- **Autores:** Agustín Vignolo y Florencia Mendoza (Grupo 8, N8B)

## Problema

El dataset de MercaNova trae el catálogo (productos, marcas, categorías, especificaciones y relaciones), los precios y el stock por depósito. No trae nada sobre lo que hace el usuario en la tienda: no hay carritos, ni órdenes, ni conversaciones con el asistente.

La letra pide justamente eso. Pide persistir la información operacional (disponibilidad, carrito y órdenes) y completar una compra ficticia de punta a punta:

- generar una orden con número propio al comprar (RF-14),
- descontar del stock las unidades vendidas (RF-15),
- mostrarle al usuario el historial de sus órdenes (RF-16).

Además, el asistente tiene que recordar la conversación entre un mensaje y el siguiente.

Hay que decidir qué tablas nuevas agregar y cómo se comportan. El modelo completo está en `docs/diagrams/modelo-de-datos.md`.

## Alternativas

Hubo tres preguntas, cada una con dos opciones.

**1. Dónde guardar el carrito**

| Opción | A favor | En contra |
|---|---|---|
| En el navegador (`localStorage`) [1] | No necesita tablas. Responde sin ir al servidor. | El asistente no puede leer ni modificar el carrito, porque corre en el backend. Al validar stock el backend tendría que confiar en lo que manda el navegador. Se pierde si el usuario borra los datos del navegador. |
| **En la base de datos (elegida)** | Una sola versión del carrito: la que ve la pantalla es la misma que usa el asistente. El backend valida el stock contra datos propios. | Dos tablas más (`carts`, `cart_items`) y un pedido al servidor por cada cambio. |

**2. Cuándo descontar o reservar el stock**

| Opción | A favor | En contra |
|---|---|---|
| Reservar al agregar al carrito | El usuario tiene asegurada la unidad mientras decide. | Carritos abandonados bloquean stock que nadie compra. Hay que programar un vencimiento de reservas. |
| **Validar al agregar y descontar recién al confirmar (elegida)** | El stock solo cambia cuando hay una compra real. Al confirmar se vuelve a validar todo dentro de una transacción con bloqueo de filas [2], así dos compras simultáneas no venden la misma unidad. | Puede pasar que el producto se agote entre que se agrega y se confirma. En ese caso se le avisa al usuario con un error claro (`INSUFFICIENT_STOCK`). |

**3. Cómo guardar el precio de cada línea de la orden**

| Opción | A favor | En contra |
|---|---|---|
| Por referencia: la línea apunta al producto y el precio se lee de `prices` | No se duplica información. | Si el precio cambia, una orden ya confirmada mostraría un precio distinto al que se pagó. El historial dejaría de ser confiable. |
| **Copiado: la línea guarda el nombre y el precio del momento (elegida)** | El historial muestra exactamente lo que pagó el usuario, aunque después cambie el catálogo. | Se repiten el nombre y el precio en cada línea. |

## Decisión

Agregamos siete tablas que no están en el dataset:

| Tabla | Qué guarda |
|---|---|
| `carts` | Un carrito por sesión del navegador |
| `cart_items` | Los productos del carrito y su cantidad (al menos 1) |
| `orders` | La orden: estado, datos del cliente, forma de entrega, total y fechas |
| `order_items` | Las líneas de la orden, con el nombre y el precio unitario copiados al crearla |
| `order_allocations` | Cuántas unidades de cada línea salieron de cada depósito al confirmar |
| `conversations` | Una conversación con el asistente, asociada a la sesión |
| `messages` | Cada mensaje, con su rol, el texto, los bloques visuales y las herramientas usadas |

Además:

- El stock **no se reserva** en el carrito. Se valida al agregar y se descuenta al confirmar.
- La orden tiene tres estados posibles: `pending_confirmation`, `confirmed` y `cancelled`. La base rechaza cualquier otro valor.
- La base también rechaza stock disponible negativo, cantidades menores a 1 en el carrito y órdenes con retiro en depósito que no indican el depósito.

## Justificación

- **Persistencia que pide la letra.** El carrito y las órdenes quedan en la base, junto con el stock. Sobreviven a que el usuario recargue la página o cierre el navegador.
- **Estado coherente entre operaciones.** El carrito que se ve en pantalla y el que usa el asistente son el mismo registro. Cuando el asistente agrega un producto, la pantalla lo muestra sin pasos extra.
- **Stock real y sin ventas dobles.** Descontar solo al confirmar, dentro de una transacción con bloqueo de filas, garantiza que el stock nunca quede negativo, como pide la actualización de stock (RF-15). La restricción `available_qty >= 0` en `inventory` es una segunda barrera: aunque falle el código, la base no acepta el dato [3].
- **Historial fiel.** `order_items` copia el precio al crear la orden. El historial de órdenes (RF-16) muestra lo que se pagó, no el precio de hoy. Si el precio cambia entre que se arma la orden y se confirma, el backend lo detecta comparando contra esa copia y avisa con `PRICE_CHANGED`, como define el contrato de la API (`docs/api-contract.md`).
- **Trazabilidad del stock.** `order_allocations` registra de qué depósito salió cada unidad. Con envío a domicilio el stock puede salir de más de un depósito. Esta tabla permite explicar cada descuento de stock y revisarlo después.
- **Conversación recuperable.** `messages` guarda los bloques visuales y las herramientas que usó el asistente. Así se puede restaurar el chat y mostrar en qué datos se basó cada respuesta.

## Costos y riesgos (trade-offs)

- **Más tablas y más consultas.** Cada cambio en el carrito es un pedido al servidor. Para un prototipo local la demora es despreciable.
- **El producto se puede agotar antes de confirmar.** Como no hay reserva, el usuario puede recibir un aviso de stock insuficiente al confirmar. Lo preferimos a bloquear stock con carritos abandonados.
- **Datos repetidos en las órdenes.** El nombre y el precio están copiados en `order_items`. Es el costo de tener un historial confiable.
- **Sin usuarios.** Todo se asocia al identificador de sesión del navegador, porque la letra deja el login fuera del alcance. Si el usuario borra los datos del navegador, pierde el acceso a su carrito y sus órdenes. En producción habría una tabla de usuarios y `session_id` pasaría a ser una clave foránea.
- **Órdenes pendientes sin limpiar.** Las órdenes que nadie confirma quedan guardadas. No afectan el stock porque no lo reservan. En producción se borrarían con una tarea periódica.

## Fuentes

1. MDN Web Docs, *Window: localStorage property*: https://developer.mozilla.org/en-US/docs/Web/API/Window/localStorage
2. PostgreSQL 16, *Explicit Locking* (bloqueo de filas con `SELECT ... FOR UPDATE`): https://www.postgresql.org/docs/16/explicit-locking.html
3. PostgreSQL 16, *Constraints* (restricciones `CHECK` y claves foráneas): https://www.postgresql.org/docs/16/ddl-constraints.html
