import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { describe, expect, it, vi } from 'vitest'
import type { CartItem } from '../../../api/types'
import { CartLineItem } from './CartLineItem'

const item: CartItem = {
  product_id: 'MN-MON-0001',
  name: 'Flux Vision 24 QHD IPS',
  image_url: '/m1.jpg',
  unit_price: 100,
  quantity: 2,
  line_total: 200,
  available_qty: 5,
}

function setup(overrides: Partial<CartItem> = {}, props: { disabled?: boolean } = {}) {
  const onChangeQuantity = vi.fn()
  const onRemove = vi.fn()
  render(
    <MemoryRouter>
      <CartLineItem
        item={{ ...item, ...overrides }}
        currency="USD"
        onChangeQuantity={onChangeQuantity}
        onRemove={onRemove}
        {...props}
      />
    </MemoryRouter>,
  )
  return { onChangeQuantity, onRemove, user: userEvent.setup() }
}

describe('CartLineItem', () => {
  it('shows the product link, prices and quantity', () => {
    setup()

    expect(screen.getByRole('link', { name: 'Flux Vision 24 QHD IPS' })).toHaveAttribute('href', '/products/MN-MON-0001')
    expect(screen.getByText('2')).toBeInTheDocument()
    expect(screen.getByText(/100,00/)).toBeInTheDocument()
    expect(screen.getByText(/200,00/)).toBeInTheDocument()
    expect(document.querySelector('img')).toHaveAttribute('src', '/m1.jpg')
  })

  it('renders a placeholder instead of an image when there is none', () => {
    setup({ image_url: null })

    expect(document.querySelector('img')).toBeNull()
  })

  it('asks for quantity + 1 and quantity - 1', async () => {
    const { onChangeQuantity, user } = setup()

    await user.click(screen.getByRole('button', { name: 'Agregar una unidad de Flux Vision 24 QHD IPS' }))
    await user.click(screen.getByRole('button', { name: 'Quitar una unidad de Flux Vision 24 QHD IPS' }))

    expect(onChangeQuantity).toHaveBeenNthCalledWith(1, 3)
    expect(onChangeQuantity).toHaveBeenNthCalledWith(2, 1)
  })

  it('disables minus at 1 unit', () => {
    setup({ quantity: 1, line_total: 100 })

    expect(screen.getByRole('button', { name: /Quitar una unidad/ })).toBeDisabled()
  })

  it('disables plus at the available quantity and explains why', () => {
    setup({ quantity: 5, available_qty: 5 })

    expect(screen.getByRole('button', { name: /Agregar una unidad/ })).toBeDisabled()
    expect(screen.getByText('Máximo disponible')).toBeInTheDocument()
  })

  it('does not show the hint below the limit', () => {
    setup()

    expect(screen.queryByText('Máximo disponible')).not.toBeInTheDocument()
  })

  it('removes the line with a button named after the product', async () => {
    const { onRemove, user } = setup()

    await user.click(screen.getByRole('button', { name: 'Quitar Flux Vision 24 QHD IPS del carrito' }))

    expect(onRemove).toHaveBeenCalledOnce()
  })

  it('disables every control while the line is updating', () => {
    setup({}, { disabled: true })

    for (const button of screen.getAllByRole('button')) expect(button).toBeDisabled()
  })

  it('warns when the stock went down below the quantity and lets the user lower it', async () => {
    const { user, onChangeQuantity } = setup({ quantity: 4, line_total: 400, available_qty: 2 })

    expect(screen.getByText('Ahora solo hay 2 unidades. Bajá la cantidad para poder comprar.')).toBeInTheDocument()
    expect(screen.queryByText('Máximo disponible')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Quitar una unidad de Flux Vision 24 QHD IPS' }))
    expect(onChangeQuantity).toHaveBeenCalledWith(3)
  })

  it('uses the singular when only one unit is left', () => {
    setup({ quantity: 3, line_total: 300, available_qty: 1 })

    expect(screen.getByText('Ahora solo hay 1 unidad. Bajá la cantidad para poder comprar.')).toBeInTheDocument()
  })

  it('asks to remove a product that ran out of stock', async () => {
    const { user, onRemove } = setup({ quantity: 1, line_total: 100, available_qty: 0 })

    expect(screen.getByText('Este producto se quedó sin stock. Quitalo para poder comprar.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Agregar una unidad de Flux Vision 24 QHD IPS' })).toBeDisabled()
    await user.click(screen.getByRole('button', { name: 'Quitar Flux Vision 24 QHD IPS del carrito' }))
    expect(onRemove).toHaveBeenCalledOnce()
  })

  it('shows no stock warning when the quantity is available', () => {
    setup({ quantity: 5, line_total: 500, available_qty: 5 })

    expect(screen.queryByText(/Bajá la cantidad|sin stock/)).not.toBeInTheDocument()
    expect(screen.getByText('Máximo disponible')).toBeInTheDocument()
  })
})
