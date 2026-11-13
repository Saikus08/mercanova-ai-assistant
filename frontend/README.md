# Frontend

Aplicación web de MercaNova hecha con React, Vite y TypeScript. Esta es la base del proyecto: tokens de diseño, componentes de interfaz reutilizables, tipos del contrato de la API y rutas iniciales. Todavía no tiene pantallas reales ni llamadas al backend.

Las reglas de arquitectura están en `AGENTS.md` (raíz del repositorio) y en la skill `.claude/skills/frontend-component/SKILL.md`.

## Qué hay

| Carpeta | Contenido |
|---|---|
| `src/theme/` | `tokens.ts` (colores, espaciado, bordes, tipografía, sombras, breakpoints) y `global.css` (estilos base) |
| `src/components/ui/` | Componentes base: `Button`, `Card`, `Input`, `Badge`, `Modal`, `Spinner`. Se importan desde `components/ui` |
| `src/components/` | Componentes presentacionales por funcionalidad (vacío por ahora) |
| `src/features/` | Contenedores y hooks que piden datos (vacío por ahora) |
| `src/pages/` | Un componente por ruta |
| `src/api/` | `types.ts`: tipos que reflejan `docs/api-contract.md` |

Rutas:

- `/`: marcador de lugar del catálogo.
- `/ui`: muestra todos los componentes base y sus variantes. Sirve para revisarlos sin abrir cada pantalla.

## Regla principal: colores y medidas solo desde tokens

Los colores, espacios, tamaños de letra, bordes y sombras se definen **solo** en `src/theme/tokens.ts`. Al iniciar la aplicación, `applyTokens()` los publica como variables CSS, y los componentes los usan así:

```css
.button {
  padding: 0 var(--space-4);
  background: var(--color-primary);
  border-radius: var(--radius-md);
}
```

No se escriben valores hexadecimales ni medidas en `px` dentro de los componentes. Si falta un valor, se agrega un token nuevo. Para revisarlo:

```bash
rg -n '#[0-9a-fA-F]{3,6}\b|[0-9]+px' src --glob '!**/theme/**'
```

El comando no debe devolver resultados.

## Cómo ejecutarlo

Con Node.js 24 instalado:

```bash
npm install
npm run dev
```

La aplicación queda en http://localhost:5173. Las llamadas a `/api` se redirigen al backend. Por defecto apuntan a `http://backend:8000`, que es el nombre del servicio dentro de Docker Compose. Si el backend corre en tu máquina, definí la variable antes de iniciar:

```bash
VITE_API_PROXY_TARGET=http://localhost:8000 npm run dev
```

Con Docker Compose, desde la raíz del repositorio:

```bash
docker compose up frontend
```

El código de `frontend/` se monta en el contenedor, así que los cambios se ven al instante.

## Pruebas y calidad

```bash
npm test -- --run   # pruebas con Vitest y Testing Library (también: make test-frontend)
npm run lint        # análisis estático con oxlint
npm run build       # verificación de tipos y compilación de producción
```
