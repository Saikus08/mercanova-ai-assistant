# Decisión 0008: Cómo prepara la compra el asistente sin ver datos personales

- **Estado:** propuesta
- **Fecha:** 16/11/2026
- **Autores:** Agustín Vignolo y Florencia Mendoza (Grupo 8, N8B)

## Problema

El usuario puede decirle al asistente "comprámelo". La letra pide que nada se compre sin una confirmación explícita (RF-12), y el caso de uso 10 pide abrir la ventana de confirmación en ese momento.

La herramienta que prepara la compra choca con otra regla del proyecto. Para crear una orden hacen falta el nombre, el email y la dirección del cliente (decisión 0002: esos tres campos son obligatorios en la tabla de órdenes). Pero esos datos personales **no deben pasar por el modelo de lenguaje ni por los registros** (regla del asistente en `AGENTS.md`; clase 7, p.12-13). Si la herramienta recibiera los datos como argumentos, el modelo los leería, y quedarían en el prompt y en la traza de la conversación.

Las dos cosas no se pueden cumplir a la vez si la herramienta crea la orden. Hay que decidir qué hace exactamente `start_checkout`.

## Alternativas

| Opción | A favor | En contra |
|---|---|---|
| **La herramienta no recibe datos personales ni crea la orden: valida el carrito y devuelve un borrador. La ventana de la interfaz pide los datos y crea la orden (elegida)** | Los datos personales nunca llegan al modelo. Mantiene el flujo de dos pasos del contrato: la orden pendiente la crea el checkout y solo el usuario la confirma. La herramienta no tiene ningún efecto sobre la base. | El contrato dice que el bloque `checkout_draft` lleva una orden pendiente. Con esta opción lleva el resumen del carrito y la orden se crea al enviar el formulario. Hay que acordar ese cambio de contrato. |
| La herramienta recibe nombre, email y dirección como argumentos y crea la orden | Una sola llamada. Coincide con el texto del contrato. | El modelo lee y repite datos personales. Quedan en el prompt, en la traza y en los registros. Contradice la regla de privacidad. |
| El usuario guarda sus datos en un perfil de la sesión y la herramienta los lee de la base | El modelo no los ve. La orden se crea en la herramienta. | Hace falta una tabla o endpoint nuevo, una pantalla para cargar el perfil y decidir cuánto tiempo se guardan. Es más alcance del que pide la letra. |

## Decisión

- **`start_checkout` no tiene argumentos.** El esquema de la herramienta no tiene ningún campo, y el dispatcher rechaza cualquier campo de más. Probado: mandar nombre y email devuelve un error.
- **No crea la orden.** Lee el carrito con los precios y el stock del momento y devuelve:
  - `ready`: verdadero si todas las cantidades alcanzan;
  - el carrito;
  - `problems`: las líneas donde la cantidad pedida supera el stock actual;
  - `next_step`: qué tiene que decirle el asistente al usuario.
- **Carrito vacío.** Devuelve un error con la pista de agregar productos primero.
- **El resto del flujo lo hace el usuario en la interfaz:** abre la ventana, completa sus datos, y el frontend llama a `POST /api/checkout` y después a `POST /api/orders/{id}/confirm` (decisión 0007).
- **Otras dos herramientas.** `view_cart` lee el carrito. `add_to_cart` agrega unidades y la sesión sale siempre del sistema, nunca de los argumentos.
- **Errores que el modelo puede corregir.** Pedir más de lo que hay devuelve "Solo hay N unidades" y sugiere una cantidad menor o alternativas. Un producto que no se vende sugiere alternativas. Un carrito vacío o una cantidad fuera de rango también traen su pista.

## Justificación

- **Datos personales fuera del modelo (clase 7, p.12-13).** El modelo no puede filtrar lo que nunca recibe. Un test comprueba que la herramienta no tiene campos, y otro que la respuesta tiene exactamente las claves especificadas.
- **Confirmación explícita (RF-12) y orden como borrador (clase 6, p.10).** La clase pone "crear una orden" entre las acciones que requieren confirmación humana. Acá ni siquiera se crea: el asistente solo prepara la ventana. La orden pendiente nace cuando el usuario envía sus datos, y se vuelve compra cuando hace clic en "Confirmar compra".
- **Prueba real.** Con el carrito cargado en la base: carrito vacío da el error con pista, agregar 2 unidades funciona, agregar 50 con 9 disponibles dice "Solo hay 9 unidades" con la sugerencia, `start_checkout` devuelve `ready: true`, y mandarle nombre y email se rechaza. Después de todo eso no había ninguna orden en la base y el stock seguía igual.

## Costos y riesgos (trade-offs)

- **Hay que acordar un cambio de contrato.** El contrato de la API describe `checkout_draft` con una orden dentro. Con esta decisión, el bloque trae el resumen del carrito y la orden se crea después, desde el formulario. Ese cambio va en un pull request aparte, revisado por las dos personas, como pide el contrato. Hasta entonces hay una diferencia entre el contrato y la implementación.
- **`ready: true` no garantiza que la orden se cree.** La herramienta compara contra el stock total. El checkout compara contra el depósito elegido si el retiro es en un depósito. Un producto puede alcanzar en total y no alcanzar en el depósito elegido. En ese caso el usuario recibe el error del checkout en la ventana.
- **No detecta productos desactivados después de agregarlos.** Solo compara cantidades. El checkout sí los rechaza al crear la orden.
- **El usuario pasa por un formulario.** No puede "comprar sin salir del chat". Es el costo de no exponer sus datos al modelo, y es lo que pide el caso de uso 10: abrir la ventana de confirmación.
- **La herramienta no puede bajar cantidades.** Si el stock no alcanza, le pide al usuario que ajuste el carrito, porque el asistente no tiene una herramienta para reducir líneas. Se puede sumar más adelante si hace falta.

## Fuentes

1. Clases del curso: clase 6 (p.9, permisos y mínimo privilegio; p.10, acciones que requieren confirmación humana) y clase 7 (p.12-13, datos personales fuera del modelo y de los registros).
2. `AGENTS.md`, reglas del asistente 2 (permisos) y 7 (guardrails, datos personales del checkout).
3. Decisiones 0002 (campos de la orden), 0005 (herramientas y dispatcher) y 0007 (compra en dos pasos).
