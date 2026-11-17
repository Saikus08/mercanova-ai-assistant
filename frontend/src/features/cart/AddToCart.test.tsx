import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { CartApi } from '../../api/cart'
import { createFakeCartApi } from '../../test/fakeCartApi'
import { renderWithShop } from '../../test/renderWithShop'
import { AddToCart } from './AddToCart'
import { CartContainer } from './CartContainer'

describe('AddToCart', () => {
  it('adds one unit and confirms it', async () => {
    const user = userEvent.setup()
    const base = createFakeCartApi()
    const addItem = vi.fn(base.addItem)
    renderWithShop(<AddToCart productId="MN-MON-0001" productName="Flux" availableQty={5} />, {
      cartApi: { ...base, addItem },
    })

    await user.click(screen.getByRole('button', { name: 'Agregar al carrito: Flux' }))

    expect(addItem).toHaveBeenCalledWith('MN-MON-0001', 1)
    expect(await screen.findByText('Agregado al carrito')).toBeInTheDocument()
  })

  it('shows "Sin stock" and does not call the API when there is no stock', async () => {
    const user = userEvent.setup()
    const addItem = vi.fn<CartApi['addItem']>()
    renderWithShop(<AddToCart productId="MN-MON-0003" productName="Flux" availableQty={0} />, {
      cartApi: { ...createFakeCartApi(), addItem },
    })

    const button = screen.getByRole('button', { name: 'Sin stock' })
    expect(button).toBeDisabled()
    await user.click(button)
    expect(addItem).not.toHaveBeenCalled()
  })

  it('shows the API message when there is not enough stock', async () => {
    const user = userEvent.setup()
    renderWithShop(<AddToCart productId="MN-HEA-0001" productName="Echo" availableQty={2} />, {
      cartApi: createFakeCartApi({ 'MN-HEA-0001': 2 }),
    })

    await user.click(screen.getByRole('button', { name: 'Agregar al carrito: Echo' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Solo hay 2 unidades disponibles.')
    expect(screen.queryByText('Agregado al carrito')).not.toBeInTheDocument()
  })

  it('updates the shared cart', async () => {
    const user = userEvent.setup()
    renderWithShop(
      <>
        <AddToCart productId="MN-MON-0001" productName="Flux" availableQty={5} />
        <CartContainer />
      </>,
    )
    expect(await screen.findByText('Tu carrito está vacío')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Agregar al carrito: Flux' }))

    expect(await screen.findByText('1 producto')).toBeInTheDocument()
  })
})
