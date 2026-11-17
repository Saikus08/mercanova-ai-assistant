import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { CatalogApi } from '../../api/catalog'
import { ApiRequestError } from '../../api/http'
import { createMockCatalogApi } from '../../api/mocks/mockCatalogApi'
import { createFakeCartApi } from '../../test/fakeCartApi'
import { renderWithCatalog } from '../../test/renderWithCatalog'
import { CatalogContainer } from './CatalogContainer'

function apiWith(overrides: Partial<CatalogApi>): CatalogApi {
  return { ...createMockCatalogApi(), ...overrides }
}

describe('CatalogContainer', () => {
  it('shows a loading state and then the products', async () => {
    renderWithCatalog(<CatalogContainer />)

    expect(screen.getByText('Cargando productos…')).toBeInTheDocument()

    const list = await screen.findByRole('list', { name: 'Productos' })
    expect(within(list).getAllByRole('listitem')).toHaveLength(7)
    expect(screen.getByText('7 productos')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Flux Vision 24 QHD IPS' })).toHaveAttribute(
      'href',
      '/products/MN-MON-0001',
    )
  })

  it('adds a product to the cart from its card', async () => {
    const user = userEvent.setup()
    const cartApi = createFakeCartApi()
    const addItem = vi.fn(cartApi.addItem)
    renderWithCatalog(<CatalogContainer />, { cartApi: { ...cartApi, addItem } })
    await screen.findByRole('list', { name: 'Productos' })

    await user.click(screen.getByRole('button', { name: 'Agregar al carrito: Flux Vision 24 QHD IPS' }))

    expect(addItem).toHaveBeenCalledWith('MN-MON-0001', 1)
    expect(await screen.findByText('Agregado al carrito')).toBeInTheDocument()
  })

  it('applies the filters from the URL to the request', async () => {
    const listProducts = vi.fn(createMockCatalogApi().listProducts)
    renderWithCatalog(<CatalogContainer />, {
      api: apiWith({ listProducts }),
      path: '/?category=Headphones&in_stock=true',
    })

    expect(await screen.findByText('2 productos')).toBeInTheDocument()
    expect(listProducts).toHaveBeenLastCalledWith(
      expect.objectContaining({ category: 'Headphones', in_stock: true }),
      expect.any(AbortSignal),
    )
  })

  it('updates the URL and the list when a filter changes', async () => {
    const user = userEvent.setup()
    renderWithCatalog(<CatalogContainer />)
    await screen.findByText('7 productos')

    await user.selectOptions(screen.getByLabelText('Categoría'), 'Laptops')

    expect(await screen.findByText('2 productos')).toBeInTheDocument()
    expect(screen.getByTestId('location')).toHaveTextContent('/?category=Laptops')
  })

  it('searches by text when the form is submitted', async () => {
    const user = userEvent.setup()
    renderWithCatalog(<CatalogContainer />)
    await screen.findByText('7 productos')

    await user.type(screen.getByLabelText('Buscar'), 'echo{Enter}')

    expect(await screen.findByText('2 productos')).toBeInTheDocument()
    expect(screen.getByTestId('location')).toHaveTextContent('/?q=echo')
  })

  it('shows an empty state with a way to clear the filters', async () => {
    const user = userEvent.setup()
    renderWithCatalog(<CatalogContainer />, { path: '/?q=playstation' })

    expect(await screen.findByText('No encontramos productos')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Quitar filtros' }))

    expect(await screen.findByText('7 productos')).toBeInTheDocument()
    expect(screen.getByTestId('location')).toHaveTextContent(/^\/$/)
  })

  it('shows the API error message and retries', async () => {
    const user = userEvent.setup()
    const working = createMockCatalogApi().listProducts
    const listProducts = vi
      .fn<CatalogApi['listProducts']>()
      .mockRejectedValueOnce(new ApiRequestError('INTERNAL_ERROR', 'La tienda no responde.', 500))
      .mockImplementation(working)
    renderWithCatalog(<CatalogContainer />, { api: apiWith({ listProducts }) })

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('No pudimos cargar los productos')
    expect(alert).toHaveTextContent('La tienda no responde.')

    await user.click(screen.getByRole('button', { name: 'Reintentar' }))
    expect(await screen.findByText('7 productos')).toBeInTheDocument()
  })

  it('still lists products when the categories cannot be loaded', async () => {
    renderWithCatalog(<CatalogContainer />, {
      api: apiWith({ listCategories: () => Promise.reject(new Error('down')) }),
    })

    expect(await screen.findByText('7 productos')).toBeInTheDocument()
    expect(screen.getByLabelText('Subcategoría')).toBeDisabled()
  })
})
