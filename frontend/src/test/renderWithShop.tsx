import { render } from '@testing-library/react'
import type { ReactElement } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router'
import type { CartApi } from '../api/cart'
import type { CatalogApi } from '../api/catalog'
import type { OrdersApi } from '../api/orders'
import type { WarehousesApi } from '../api/warehouses'
import { createMockCatalogApi } from '../api/mocks/mockCatalogApi'
import { CartApiProvider } from '../features/cart/CartApiProvider'
import { CartProvider } from '../features/cart/CartProvider'
import { CatalogApiProvider } from '../features/catalog/CatalogApiProvider'
import { CheckoutApiProvider } from '../features/checkout/CheckoutApiProvider'
import { createFakeCartApi } from './fakeCartApi'
import { createFakeOrdersApi } from './fakeOrdersApi'
import { createFakeWarehousesApi } from './fakeWarehousesApi'
import { LocationProbe } from './LocationProbe'

interface ShopOptions {
  cartApi?: CartApi
  catalogApi?: CatalogApi
  /** Defaults to a fake that builds orders from `cartApi`. */
  ordersApi?: OrdersApi
  warehousesApi?: WarehousesApi
  path?: string
  route?: string
}

/** Renders a screen with fake cart, catalog, orders and warehouses APIs, the cart provider and a router. */
export function renderWithShop(
  ui: ReactElement,
  {
    cartApi = createFakeCartApi(),
    catalogApi = createMockCatalogApi(),
    ordersApi = createFakeOrdersApi(cartApi),
    warehousesApi = createFakeWarehousesApi(),
    path = '/',
    route = '/',
  }: ShopOptions = {},
) {
  return render(
    <CatalogApiProvider api={catalogApi}>
      <CartApiProvider api={cartApi}>
        <CheckoutApiProvider ordersApi={ordersApi} warehousesApi={warehousesApi}>
          <CartProvider>
            <MemoryRouter initialEntries={[path]}>
              <Routes>
                <Route path={route} element={ui} />
                <Route path="*" element={null} />
              </Routes>
              <LocationProbe />
            </MemoryRouter>
          </CartProvider>
        </CheckoutApiProvider>
      </CartApiProvider>
    </CatalogApiProvider>,
  )
}
