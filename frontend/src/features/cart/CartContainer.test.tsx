import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { CartApi } from '../../api/cart'
import { ApiRequestError } from '../../api/http'
import { createFakeCartApi } from '../../test/fakeCartApi'
import { renderWithShop } from '../../test/renderWithShop'
import { CartContainer } from './CartContainer'

describe('CartContainer', () => {
  it('shows a loading state and then the lines with the server total', async () => {
    renderWithShop(<CartContainer />, { cartApi: createFakeCartApi({ 'MN-MON-0001': 2, 'MN-HEA-0001': 1 }) })

    expect(screen.getByText('Cargando carrito…')).toBeInTheDocument()

    const list = await screen.findByRole('list', { name: 'Productos del carrito' })
    expect(within(list).getAllByRole('listitem')).toHaveLength(2)
    expect(screen.getByText('3 productos')).toBeInTheDocument()
    expect(screen.getByText(/250,00/)).toBeInTheDocument()
  })

  it('shows the empty state', async () => {
    renderWithShop(<CartContainer />)

    expect(await screen.findByText('Tu carrito está vacío')).toBeInTheDocument()
  })

  it('shows the error and retries', async () => {
    const user = userEvent.setup()
    const base = createFakeCartApi({ 'MN-MON-0001': 1 })
    const getCart = vi
      .fn<CartApi['getCart']>()
      .mockRejectedValueOnce(new ApiRequestError('NETWORK_ERROR', 'Sin conexión.', null))
      .mockImplementation(base.getCart)
    renderWithShop(<CartContainer />, { cartApi: { ...base, getCart } })

    expect(await screen.findByRole('alert')).toHaveTextContent('Sin conexión.')
    await user.click(screen.getByRole('button', { name: 'Reintentar' }))

    expect(await screen.findByRole('list', { name: 'Productos del carrito' })).toBeInTheDocument()
  })

  it('calls the API when the quantity changes and renders the server cart', async () => {
    const user = userEvent.setup()
    const base = createFakeCartApi({ 'MN-MON-0001': 2 })
    const updateQuantity = vi.fn(base.updateQuantity)
    renderWithShop(<CartContainer />, { cartApi: { ...base, updateQuantity } })

    await user.click(await screen.findByRole('button', { name: 'Agregar una unidad de Flux Vision 24 QHD IPS' }))

    expect(updateQuantity).toHaveBeenCalledWith('MN-MON-0001', 3)
    expect(await screen.findByText('3 productos')).toBeInTheDocument()
    // line total and cart total
    expect(screen.getAllByText(/300,00/)).toHaveLength(2)
  })

  it('removes a line', async () => {
    const user = userEvent.setup()
    const base = createFakeCartApi({ 'MN-MON-0001': 1, 'MN-HEA-0001': 1 })
    const removeItem = vi.fn(base.removeItem)
    renderWithShop(<CartContainer />, { cartApi: { ...base, removeItem } })

    await user.click(await screen.findByRole('button', { name: 'Quitar Echo Calm ANC del carrito' }))

    expect(removeItem).toHaveBeenCalledWith('MN-HEA-0001')
    expect(await screen.findByText('1 producto')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Echo Calm ANC' })).not.toBeInTheDocument()
  })

  it('shows the INSUFFICIENT_STOCK message and keeps the cart', async () => {
    const user = userEvent.setup()
    const base = createFakeCartApi({ 'MN-HEA-0001': 1 })
    const updateQuantity = vi
      .fn<CartApi['updateQuantity']>()
      .mockRejectedValue(new ApiRequestError('INSUFFICIENT_STOCK', 'Solo hay 1 unidad disponible.', 409))
    renderWithShop(<CartContainer />, { cartApi: { ...base, updateQuantity } })

    await user.click(await screen.findByRole('button', { name: 'Agregar una unidad de Echo Calm ANC' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Solo hay 1 unidad disponible.')
    expect(screen.getByRole('link', { name: 'Echo Calm ANC' })).toBeInTheDocument()
    expect(screen.getByText('1 producto')).toBeInTheDocument()
  })

  it('keeps checkout disabled until a handler is provided', async () => {
    renderWithShop(<CartContainer />, { cartApi: createFakeCartApi({ 'MN-MON-0001': 1 }) })

    expect(await screen.findByRole('button', { name: 'Continuar con la compra' })).toBeDisabled()
  })

  it('starts the checkout through the onCheckout prop', async () => {
    const user = userEvent.setup()
    const onCheckout = vi.fn()
    renderWithShop(<CartContainer onCheckout={onCheckout} />, { cartApi: createFakeCartApi({ 'MN-MON-0001': 1 }) })

    await user.click(await screen.findByRole('button', { name: 'Continuar con la compra' }))

    expect(onCheckout).toHaveBeenCalledOnce()
  })
})
