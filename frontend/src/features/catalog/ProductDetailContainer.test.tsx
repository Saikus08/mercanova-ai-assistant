import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { CatalogApi } from '../../api/catalog'
import { ApiRequestError } from '../../api/http'
import { createMockCatalogApi } from '../../api/mocks/mockCatalogApi'
import { ProductDetailPage } from '../../pages/ProductDetailPage'
import { renderWithCatalog } from '../../test/renderWithCatalog'

const route = '/productos/:productId'

describe('ProductDetailContainer', () => {
  it('shows the product with price, stock per warehouse and specifications', async () => {
    renderWithCatalog(<ProductDetailPage />, { path: '/productos/MN-MON-0001', route })

    expect(
      await screen.findByRole('heading', { level: 1, name: 'Flux Vision 24 QHD IPS' }),
    ).toBeInTheDocument()
    expect(screen.getByText('14 unidades disponibles')).toBeInTheDocument()
    expect(screen.getByText('-5%')).toBeInTheDocument()
    expect(screen.getByRole('rowheader', { name: 'MercaNova Centro' })).toBeInTheDocument()
    expect(screen.getByRole('cell', { name: '240 Hz' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Flux Office 27 FHD' })).toHaveAttribute(
      'href',
      '/productos/MN-MON-0002',
    )
  })

  it('marks products without stock', async () => {
    renderWithCatalog(<ProductDetailPage />, { path: '/productos/MN-MON-0003', route })

    expect(await screen.findByText('Sin stock')).toBeInTheDocument()
    expect(screen.queryByText(/unidades disponibles/)).not.toBeInTheDocument()
  })

  it('says the product does not exist instead of showing an error', async () => {
    renderWithCatalog(<ProductDetailPage />, { path: '/productos/MN-NOPE', route })

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
      path: '/productos/MN-HEA-0001',
      route,
    })

    expect(await screen.findByRole('alert')).toHaveTextContent('Sin conexión.')
    await user.click(screen.getByRole('button', { name: 'Reintentar' }))

    expect(await screen.findByRole('heading', { level: 1, name: 'Echo Calm ANC' })).toBeInTheDocument()
  })
})
