import { render } from '@testing-library/react'
import type { ReactElement } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router'
import type { CartApi } from '../api/cart'
import type { CatalogApi } from '../api/catalog'
import type { ChatApi } from '../api/chat'
import type { OrdersApi } from '../api/orders'
import type { SpeechApi } from '../api/speech'
import type { WarehousesApi } from '../api/warehouses'
import { createMockCatalogApi } from '../api/mocks/mockCatalogApi'
import { CartApiProvider } from '../features/cart/CartApiProvider'
import { CartProvider } from '../features/cart/CartProvider'
import { CatalogApiProvider } from '../features/catalog/CatalogApiProvider'
import { ChatApiProvider } from '../features/chat/ChatApiProvider'
import { ChatProvider } from '../features/chat/ChatProvider'
import { SpeechApiProvider } from '../features/chat/SpeechApiProvider'
import { CheckoutApiProvider } from '../features/checkout/CheckoutApiProvider'
import { createFakeCartApi } from './fakeCartApi'
import { createFakeChatApi } from './fakeChatApi'
import { createFakeOrdersApi } from './fakeOrdersApi'
import { createFakeSpeechApi } from './fakeSpeechApi'
import { createFakeWarehousesApi } from './fakeWarehousesApi'
import { LocationProbe } from './LocationProbe'

interface ShopOptions {
  cartApi?: CartApi
  catalogApi?: CatalogApi
  /** Defaults to a fake that builds orders from `cartApi`. */
  ordersApi?: OrdersApi
  warehousesApi?: WarehousesApi
  chatApi?: ChatApi
  speechApi?: SpeechApi
  path?: string
  route?: string
}

/** Renders a screen with fake cart, catalog, orders, warehouses, chat and voice APIs, the cart and chat providers and a router. */
export function renderWithShop(
  ui: ReactElement,
  {
    cartApi = createFakeCartApi(),
    catalogApi = createMockCatalogApi(),
    ordersApi = createFakeOrdersApi(cartApi),
    warehousesApi = createFakeWarehousesApi(),
    chatApi = createFakeChatApi(),
    speechApi = createFakeSpeechApi(),
    path = '/',
    route = '/',
  }: ShopOptions = {},
) {
  return render(
    <CatalogApiProvider api={catalogApi}>
      <CartApiProvider api={cartApi}>
        <CheckoutApiProvider ordersApi={ordersApi} warehousesApi={warehousesApi}>
          <ChatApiProvider api={chatApi}>
            <SpeechApiProvider api={speechApi}>
              <CartProvider>
                <ChatProvider>
                  <MemoryRouter initialEntries={[path]}>
                    <Routes>
                      <Route path={route} element={ui} />
                      <Route path="*" element={null} />
                    </Routes>
                    <LocationProbe />
                  </MemoryRouter>
                </ChatProvider>
              </CartProvider>
            </SpeechApiProvider>
          </ChatApiProvider>
        </CheckoutApiProvider>
      </CartApiProvider>
    </CatalogApiProvider>,
  )
}
