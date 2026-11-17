import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { ApiRequestError } from '../../api/http'
import { createFakeCartApi } from '../../test/fakeCartApi'
import { createFakeOrdersApi } from '../../test/fakeOrdersApi'
import { confirmedOrder } from '../../test/orderFixtures'
import { renderWithShop } from '../../test/renderWithShop'
import { OrderDetailContainer } from './OrderDetailContainer'

const cartApi = createFakeCartApi()

describe('OrderDetailContainer', () => {
  it('shows the order with a link back to the list', async () => {
    const ordersApi = createFakeOrdersApi(cartApi, [confirmedOrder])
    renderWithShop(<OrderDetailContainer orderId="ORD-20261112-0002" />, { ordersApi })

    expect(await screen.findByRole('heading', { level: 1, name: /ORD-20261112-0002/ })).toBeInTheDocument()
    expect(screen.getByText('Flux Vision 24')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Volver a mis compras/ })).toHaveAttribute('href', '/orders')
  })

  it('shows a spinner while loading', () => {
    const ordersApi = { ...createFakeOrdersApi(cartApi), get: () => new Promise<never>(() => {}) }
    renderWithShop(<OrderDetailContainer orderId="ORD-1" />, { ordersApi })

    expect(screen.getByText(/Cargando/)).toBeInTheDocument()
  })

  it('says the order does not exist for ORDER_NOT_FOUND', async () => {
    renderWithShop(<OrderDetailContainer orderId="ORD-NOPE" />, { ordersApi: createFakeOrdersApi(cartApi) })

    expect(await screen.findByText('La orden no existe.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Reintentar' })).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Volver a mis compras/ })).toHaveAttribute('href', '/orders')
  })

  it('shows the API message on other errors and retries', async () => {
    const user = userEvent.setup()
    const get = vi
      .fn()
      .mockRejectedValueOnce(new ApiRequestError('NETWORK_ERROR', 'No pudimos conectarnos con la tienda.', null))
      .mockResolvedValueOnce(confirmedOrder)
    renderWithShop(<OrderDetailContainer orderId="ORD-20261112-0002" />, {
      ordersApi: { ...createFakeOrdersApi(cartApi), get },
    })

    expect(await screen.findByRole('alert')).toHaveTextContent('No pudimos conectarnos con la tienda.')
    await user.click(screen.getByRole('button', { name: 'Reintentar' }))

    expect(await screen.findByRole('heading', { level: 1, name: /ORD-20261112-0002/ })).toBeInTheDocument()
    expect(get).toHaveBeenCalledTimes(2)
  })
})
