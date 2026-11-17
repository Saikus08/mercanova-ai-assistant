import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { CatalogApi } from '../../api/catalog'
import { ApiRequestError } from '../../api/http'
import { createMockCatalogApi } from '../../api/mocks/mockCatalogApi'
import { ProductDetailPage } from '../../pages/ProductDetailPage'
import { createFakeCartApi } from '../../test/fakeCartApi'
import { renderWithCatalog } from '../../test/renderWithCatalog'

const route = '/products/:productId'

describe('ProductDetailContainer', () => {
  it('shows the product with price, stock per warehouse and specifications', async () => {
    renderWithCatalog(<ProductDetailPage />, { path: '/products/MN-MON-0001', route })

    expect(
      await screen.findByRole('heading', { level: 1, name: 'Flux Vision 24 QHD IPS' }),
    ).toBeInTheDocument()
    expect(screen.getByText('14 unidades disponibles')).toBeInTheDocument()
    expect(screen.getByText('-5%')).toBeInTheDocument()
    expect(screen.getByRole('rowheader', { name: 'MercaNova Centro' })).toBeInTheDocument()
    expect(screen.getByRole('cell', { name: '240 Hz' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Flux Office 27 FHD' })).toHaveAttribute(
      'href',
      '/products/MN-MON-0002',
    )
  })

  it('marks products without stock', async () => {
    renderWithCatalog(<ProductDetailPage />, { path: '/products/MN-MON-0003', route })

    // The stock badge and the disabled add-to-cart button both say "Sin stock".
    expect(await screen.findByRole('button', { name: 'Sin stock' })).toBeDisabled()
    expect(screen.getAllByText('Sin stock')).toHaveLength(2)
    expect(screen.queryByText(/unidades disponibles/)).not.toBeInTheDocument()
  })

  it('adds the product to the cart from the detail', async () => {
    const user = userEvent.setup()
    const cartApi = createFakeCartApi()
    const addItem = vi.fn(cartApi.addItem)
    renderWithCatalog(<ProductDetailPage />, {
      cartApi: { ...cartApi, addItem },
      path: '/products/MN-MON-0001',
      route,
    })

    await user.click(await screen.findByRole('button', { name: 'Agregar al carrito: Flux Vision 24 QHD IPS' }))

    expect(addItem).toHaveBeenCalledWith('MN-MON-0001', 1)
    expect(await screen.findByText('Agregado al carrito')).toBeInTheDocument()
  })

  it('says the product does not exist instead of showing an error', async () => {
    renderWithCatalog(<ProductDetailPage />, { path: '/products/MN-NOPE', route })

    expect(await screen.findByText('Este producto no existe')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Reintentar' })).not.toBeInTheDocument()
  })

  it('shows the error message and retries', async () => {
    const user = userEvent.setup()
    const getProduct = vi
      .fn<CatalogApi['getProduct']>()
      .mockRejectedValueOnce(new ApiRequestError('NETWORK_ERROR', 'Sin conexión.', null))
      .mockImplementation(createMockCatalogApi().getProduct)
    renderWithCatalog(<ProductDetailPage />, {
      api: { ...createMockCatalogApi(), getProduct },
      path: '/products/MN-HEA-0001',
      route,
    })

    expect(await screen.findByRole('alert')).toHaveTextContent('Sin conexión.')
    await user.click(screen.getByRole('button', { name: 'Reintentar' }))

    expect(await screen.findByRole('heading', { level: 1, name: 'Echo Calm ANC' })).toBeInTheDocument()
  })
})
