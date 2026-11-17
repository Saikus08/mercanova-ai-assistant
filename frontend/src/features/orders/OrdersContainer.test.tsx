import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { ApiRequestError } from '../../api/http'
import type { OrdersApi } from '../../api/orders'
import { createFakeCartApi } from '../../test/fakeCartApi'
import { createFakeOrdersApi } from '../../test/fakeOrdersApi'
import { cancelledOrder, confirmedOrder, pendingOrder } from '../../test/orderFixtures'
import { renderWithShop } from '../../test/renderWithShop'
import { OrdersContainer } from './OrdersContainer'

const cartApi = createFakeCartApi()

describe('OrdersContainer', () => {
  it('shows a spinner while loading', () => {
    const ordersApi: OrdersApi = { ...createFakeOrdersApi(cartApi), list: () => new Promise(() => {}) }
    renderWithShop(<OrdersContainer />, { ordersApi })

    expect(screen.getByText(/Cargando/)).toBeInTheDocument()
  })

  it('lists the orders newest first, as the API gives them', async () => {
    const ordersApi = createFakeOrdersApi(cartApi, [confirmedOrder, pendingOrder, cancelledOrder])
    renderWithShop(<OrdersContainer />, { ordersApi })

    const rows = within(await screen.findByRole('list', { name: 'Mis compras' })).getAllByRole('listitem')
    expect(rows.map((row) => within(row).getByRole('link').textContent)).toEqual([
      'ORD-20261112-0002',
      'ORD-20261112-0001',
      'ORD-20261111-0007',
    ])
    expect(screen.getByText('Cancelada')).toBeInTheDocument()
  })

  it('invites to shop when there are no orders', async () => {
    renderWithShop(<OrdersContainer />, { ordersApi: createFakeOrdersApi(cartApi) })

    expect(await screen.findByText('Todavía no hiciste compras')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Ir al catálogo' })).toHaveAttribute('href', '/')
  })

  it('shows the API message on error and retries', async () => {
    const user = userEvent.setup()
    const list = vi
      .fn()
      .mockRejectedValueOnce(new ApiRequestError('NETWORK_ERROR', 'No pudimos conectarnos con la tienda.', null))
      .mockResolvedValueOnce([confirmedOrder])
    renderWithShop(<OrdersContainer />, { ordersApi: { ...createFakeOrdersApi(cartApi), list } })

    expect(await screen.findByRole('alert')).toHaveTextContent('No pudimos conectarnos con la tienda.')
    await user.click(screen.getByRole('button', { name: 'Reintentar' }))

    expect(await screen.findByRole('list', { name: 'Mis compras' })).toBeInTheDocument()
    expect(list).toHaveBeenCalledTimes(2)
  })
})
