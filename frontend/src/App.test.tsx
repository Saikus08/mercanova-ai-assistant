import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'
import { createMockCatalogApi } from './api/mocks/mockCatalogApi'
import { App } from './App'
import type { CartApi } from './api/cart'
import { CartApiProvider } from './features/cart/CartApiProvider'
import { CartProvider } from './features/cart/CartProvider'
import { CatalogApiProvider } from './features/catalog/CatalogApiProvider'
import { createFakeCartApi } from './test/fakeCartApi'

function renderAt(path: string, cartApi: CartApi = createFakeCartApi()) {
  return render(
    <CatalogApiProvider api={createMockCatalogApi()}>
      <CartApiProvider api={cartApi}>
        <CartProvider>
          <MemoryRouter initialEntries={[path]}>
            <App />
          </MemoryRouter>
        </CartProvider>
      </CartApiProvider>
    </CatalogApiProvider>,
  )
}

describe('App routes', () => {
  it('shows the catalog on /', async () => {
    renderAt('/')

    expect(screen.getByRole('heading', { name: 'Catálogo' })).toBeInTheDocument()
    expect(await screen.findByRole('list', { name: 'Productos' })).toBeInTheDocument()
  })

  it('shows a product detail on /products/:productId', async () => {
    renderAt('/products/MN-HEA-0001')

    expect(await screen.findByRole('heading', { level: 1, name: 'Echo Calm ANC' })).toBeInTheDocument()
  })

  it('shows the UI showcase on /ui', () => {
    renderAt('/ui')

    expect(screen.getByRole('heading', { name: 'Componentes de interfaz' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Abrir modal' })).toBeInTheDocument()
  })

  it('shows the cart on /cart', async () => {
    renderAt('/cart', createFakeCartApi({ 'MN-MON-0001': 1 }))

    expect(await screen.findByRole('heading', { level: 1, name: 'Carrito' })).toBeInTheDocument()
    expect(await screen.findByRole('list', { name: 'Productos del carrito' })).toBeInTheDocument()
  })
})

describe('App header cart link', () => {
  it('shows the item count and links to the cart', async () => {
    renderAt('/', createFakeCartApi({ 'MN-MON-0001': 2, 'MN-HEA-0001': 1 }))

    const link = await screen.findByRole('link', { name: 'Carrito, 3 productos' })
    expect(link).toHaveAttribute('href', '/cart')
    expect(link).toHaveTextContent('3')
  })

  it('uses the singular for one product', async () => {
    renderAt('/', createFakeCartApi({ 'MN-MON-0001': 1 }))

    expect(await screen.findByRole('link', { name: 'Carrito, 1 producto' })).toBeInTheDocument()
  })

  it('shows a plain link when the cart is empty', async () => {
    renderAt('/')

    expect(await screen.findByRole('link', { name: 'Carrito' })).toHaveAttribute('href', '/cart')
  })
})
