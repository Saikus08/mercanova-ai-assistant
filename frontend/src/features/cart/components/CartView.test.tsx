import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { describe, expect, it, vi } from 'vitest'
import type { Cart } from '../../../api/types'
import { CartView, type CartViewProps } from './CartView'

const cart: Cart = {
  items: [
    { product_id: 'A', name: 'Producto A', image_url: null, unit_price: 100, quantity: 2, line_total: 200, available_qty: 5 },
    { product_id: 'B', name: 'Producto B', image_url: null, unit_price: 50, quantity: 1, line_total: 50, available_qty: 1 },
  ],
  item_count: 3,
  total: 250,
  currency: 'USD',
}

function setup(props: Partial<CartViewProps> = {}) {
  const handlers = {
    onChangeQuantity: vi.fn(),
    onRemove: vi.fn(),
    onCheckout: vi.fn(),
    onDismissError: vi.fn(),
  }
  render(
    <MemoryRouter>
      <CartView cart={cart} pendingProductIds={[]} actionError={null} {...handlers} {...props} />
    </MemoryRouter>,
  )
  return { ...handlers, user: userEvent.setup() }
}

describe('CartView', () => {
  it('lists the lines and the summary', () => {
    setup()

    const list = screen.getByRole('list', { name: 'Productos del carrito' })
    expect(within(list).getAllByRole('listitem')).toHaveLength(2)
    expect(screen.getByText('3 productos')).toBeInTheDocument()
  })

  it('reports line changes with the product id', async () => {
    const { onChangeQuantity, onRemove, user } = setup()

    await user.click(screen.getByRole('button', { name: 'Agregar una unidad de Producto A' }))
    await user.click(screen.getByRole('button', { name: 'Quitar Producto B del carrito' }))

    expect(onChangeQuantity).toHaveBeenCalledWith('A', 3)
    expect(onRemove).toHaveBeenCalledWith('B')
  })

  it('only blocks the line that is updating', () => {
    setup({ pendingProductIds: ['A'] })

    expect(screen.getByRole('button', { name: 'Quitar Producto A del carrito' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Quitar Producto B del carrito' })).toBeEnabled()
  })

  it('shows the empty state with a link to the catalog', () => {
    setup({ cart: { items: [], item_count: 0, total: 0, currency: 'USD' } })

    expect(screen.getByText('Tu carrito está vacío')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Ver el catálogo' })).toHaveAttribute('href', '/')
    expect(screen.queryByRole('button', { name: 'Continuar con la compra' })).not.toBeInTheDocument()
  })

  it('shows the action error in an alert and can dismiss it', async () => {
    const { onDismissError, user } = setup({ actionError: 'Solo hay 1 unidad disponible.' })

    expect(screen.getByRole('alert')).toHaveTextContent('Solo hay 1 unidad disponible.')
    await user.click(screen.getByRole('button', { name: 'Cerrar aviso' }))
    expect(onDismissError).toHaveBeenCalledOnce()
  })

  it('starts the checkout from the summary', async () => {
    const { onCheckout, user } = setup()

    await user.click(screen.getByRole('button', { name: 'Continuar con la compra' }))

    expect(onCheckout).toHaveBeenCalledOnce()
  })
})
