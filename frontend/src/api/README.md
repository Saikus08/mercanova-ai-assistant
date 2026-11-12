# api/

Cliente tipado de la API del backend.

- `types.ts`: tipos que reflejan el contrato de la API (`docs/api-contract.md`). Si el contrato cambia, se actualiza en el mismo pull request.
- Próximamente: una función por endpoint (por ejemplo `getProducts`, `addCartItem`) que agrega el encabezado `X-Session-Id` y convierte las respuestas de error al tipo `ApiError`.

Mientras el backend no esté listo, los componentes se prueban con datos simulados que respetan estos tipos.
