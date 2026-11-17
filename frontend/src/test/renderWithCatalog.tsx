import type { ReactElement } from 'react'
import type { CartApi } from '../api/cart'
import type { CatalogApi } from '../api/catalog'
import { createMockCatalogApi } from '../api/mocks/mockCatalogApi'
import { createFakeCartApi } from './fakeCartApi'
import { renderWithShop } from './renderWithShop'

/** Catalog screens also render the add-to-cart button, so this wraps them with the cart too. */
export function renderWithCatalog(
  ui: ReactElement,
  {
    api = createMockCatalogApi(),
    cartApi = createFakeCartApi(),
    path = '/',
    route = '/',
  }: { api?: CatalogApi; cartApi?: CartApi; path?: string; route?: string } = {},
) {
  return renderWithShop(ui, { catalogApi: api, cartApi, path, route })
}
