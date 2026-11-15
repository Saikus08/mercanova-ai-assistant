---
name: frontend-component
description: Create or modify React UI components and screens following the design-token and container/presentational conventions. Use for any task labeled area:frontend.
---

# Frontend component

## Structure

```
frontend/src/
  theme/tokens.ts          colors, spacing, radius, typography — the ONLY place for raw values
  components/ui/           shared atoms/molecules: Button, Card, Input, Badge, Modal (presentational)
  features/<feature>/      everything of one feature together:
    components/            its presentational components (ProductCard, CartLine)
    containers, hooks      data fetching (useCart, useChat)
  pages/                   route-level composition only
  routes/                  routes.tsx (route table) and paths.ts (URL builders)
  lib/                     pure helpers shared across features (formatting, parsing)
  api/                     typed API client (one function per endpoint) and its types
```

`App.tsx` only renders the layout and `<AppRoutes />`; it never declares routes.

## Rules

1. **No hard-coded colors, sizes or fonts.** Import from `theme/tokens.ts`. Adding a token is fine; inlining a hex value is not.
2. **Presentational components** receive data and callbacks via props, have no side effects and no fetching.
3. **Containers/hooks** own data fetching, loading and error states.
4. Every async view handles three states: loading, error (readable Spanish message), empty.
5. Purchase confirmation must be an explicit modal with a "Confirmar compra" button. Never auto-confirm from chat.
6. Accessibility: buttons are `<button>`, inputs have labels, the voice button has `aria-label`.
7. UI copy in Spanish; code, file names and URLs in English (`/products/:productId`, not `/productos/:id`).
8. Routes are declared once in `routes/routes.tsx`; links build URLs with `routes/paths.ts`. No inline path strings in components.
9. A feature's components live inside `features/<feature>/`. Only components used by several features go to `components/ui/`. Pure helpers shared by several features go to `lib/`, not inside a feature or `components/`.
10. Component and file names in English and one component per file.

## Steps

1. Read the issue and identify the screen/flow and API endpoints involved.
2. Build or reuse UI atoms first, then the feature component, then the container.
3. Add a Vitest + Testing Library test for the component's main behavior.
4. Run `make test-frontend` and `npm run lint` before opening the PR.
