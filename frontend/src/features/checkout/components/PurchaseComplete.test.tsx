import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'
import type { Order } from '../../../api/types'
import { PurchaseComplete } from './PurchaseComplete'

const order: Order = {
  order_id: 'ORD-20261112-0001',
  status: 'confirmed',
  created_at: '2026-11-12T22:00:00Z',
  confirmed_at: '2026-11-12T22:05:00Z',
  customer: { name: 'Ana Pérez', email: 'ana@example.com', address: 'Calle 1' },
  delivery: { method: 'shipping' },
  items: [{ product_id: 'P1', name: 'Flux Vision 24', unit_price: 100, quantity: 2, line_total: 200 }],
  total: 200,
  currency: 'USD',
}

describe('PurchaseComplete', () => {
  it('confirms the purchase with the order id and the summary', () => {
    render(
      <MemoryRouter>
        <PurchaseComplete order={order} />
      </MemoryRouter>,
    )

    expect(screen.getByRole('heading', { name: '¡Compra confirmada!' })).toBeInTheDocument()
    expect(screen.getByText('ORD-20261112-0001')).toBeInTheDocument()
    expect(screen.getByText('Flux Vision 24')).toBeInTheDocument()
  })

  it('links to the order history', () => {
    render(
      <MemoryRouter>
        <PurchaseComplete order={order} />
      </MemoryRouter>,
    )

    expect(screen.getByRole('link', { name: 'Ver mis compras' })).toHaveAttribute('href', '/orders')
  })

  it('links to the catalog by default and accepts another target', () => {
    const { rerender } = render(
      <MemoryRouter>
        <PurchaseComplete order={order} />
      </MemoryRouter>,
    )
    expect(screen.getByRole('link', { name: 'Seguir comprando' })).toHaveAttribute('href', '/')

    rerender(
      <MemoryRouter>
        <PurchaseComplete order={order} catalogPath="/somewhere" />
      </MemoryRouter>,
    )
    expect(screen.getByRole('link', { name: 'Seguir comprando' })).toHaveAttribute('href', '/somewhere')
  })
})
