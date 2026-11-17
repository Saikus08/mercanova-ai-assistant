import { render } from '@testing-library/react'
import type { ReactElement } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router'
import type { CartApi } from '../api/cart'
import type { CatalogApi } from '../api/catalog'
import { createMockCatalogApi } from '../api/mocks/mockCatalogApi'
import { CartApiProvider } from '../features/cart/CartApiProvider'
import { CartProvider } from '../features/cart/CartProvider'
import { CatalogApiProvider } from '../features/catalog/CatalogApiProvider'
import { createFakeCartApi } from './fakeCartApi'
import { LocationProbe } from './LocationProbe'

interface ShopOptions {
  cartApi?: CartApi
  catalogApi?: CatalogApi
  path?: string
  route?: string
}

/** Renders a screen with fake cart and catalog APIs, the cart provider and a router. */
export function renderWithShop(
  ui: ReactElement,
  { cartApi = createFakeCartApi(), catalogApi = createMockCatalogApi(), path = '/', route = '/' }: ShopOptions = {},
) {
  return render(
    <CatalogApiProvider api={catalogApi}>
      <CartApiProvider api={cartApi}>
        <CartProvider>
          <MemoryRouter initialEntries={[path]}>
            <Routes>
              <Route path={route} element={ui} />
              <Route path="*" element={null} />
            </Routes>
            <LocationProbe />
          </MemoryRouter>
        </CartProvider>
      </CartApiProvider>
    </CatalogApiProvider>,
  )
}
