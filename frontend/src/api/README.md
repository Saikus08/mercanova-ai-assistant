# api/

Cliente tipado de la API del backend.

- `types.ts`: tipos que reflejan el contrato de la API (`docs/api-contract.md`). Si el contrato cambia, se actualiza en el mismo pull request.
- `http.ts`: hace los pedidos a `/api`, agrega el encabezado `X-Session-Id` y convierte las respuestas de error en un `ApiRequestError` con el mensaje en español del contrato. Si no hay conexión, usa un mensaje propio.
- `session.ts`: genera el identificador de sesión la primera vez y lo guarda en el navegador.
- `catalog.ts`: endpoints del catálogo (`/api/products`, `/api/products/{id}`, `/api/categories`).
- `cart.ts`: endpoints del carrito (`/api/cart`, `/api/cart/items`). Usa `apiGet`, `apiPost`, `apiPatch` y `apiDelete` de `http.ts`. No tiene datos simulados: los tests usan implementaciones en memoria de `CartApi`.
- `orders.ts`: endpoints de la compra en dos pasos (`POST /api/checkout`, `/api/orders/{id}/confirm` y `/api/orders/{id}/cancel`). Además `list` (`GET /api/orders`, historial de la sesión, más nueva primero) y `get` (`GET /api/orders/{id}`, devuelve `ORDER_NOT_FOUND` si la orden no existe o es de otra sesión).
- `chat.ts`: endpoints del asistente. `stream` llama a `POST /api/chat/stream` y lee los eventos (*Server-Sent Events*) con `fetch`, porque `EventSource` no permite POST. `send` llama a `POST /api/chat`, la respuesta completa de una vez. El lector de eventos (`createSseParser`) soporta eventos partidos entre fragmentos de la respuesta.
- `warehouses.ts`: depósitos (`GET /api/warehouses`), para elegir dónde retirar la compra.
- `mocks/`: datos simulados que respetan los tipos, con los mismos filtros que el contrato.

## Datos simulados o backend real

Mientras el backend no tenga los endpoints del catálogo, el frontend puede usar los datos simulados. Se activan con una variable de entorno al levantar Vite:

```bash
VITE_USE_MOCKS=true npm run dev
```

Sin esa variable, el frontend llama al backend real a través del proxy de Vite (`VITE_API_PROXY_TARGET`). Los tests no dependen de la variable: cada test elige la implementación con `CatalogApiProvider`.
