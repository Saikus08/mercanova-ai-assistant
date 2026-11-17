import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { Order } from '../../../api/types'
import { OrderSummary } from './OrderSummary'

const order: Order = {
  order_id: 'ORD-1',
  status: 'pending_confirmation',
  created_at: '2026-11-12T22:00:00Z',
  confirmed_at: null,
  customer: { name: 'Ana Pérez', email: 'ana@example.com', address: 'Calle 1' },
  delivery: { method: 'pickup', warehouse_id: 'WH-1' },
  items: [
    { product_id: 'P1', name: 'Flux Vision 24', unit_price: 100, quantity: 2, line_total: 200 },
    { product_id: 'P2', name: 'Echo Calm ANC', unit_price: 50, quantity: 1, line_total: 50 },
  ],
  total: 250,
  currency: 'USD',
}

describe('OrderSummary', () => {
  it('lists every item with unit price, quantity and line total', () => {
    render(<OrderSummary order={order} />)

    const items = within(screen.getByRole('list', { name: 'Productos de la orden' })).getAllByRole('listitem')
    expect(items).toHaveLength(2)
    expect(items[0]).toHaveTextContent('Flux Vision 24')
    expect(items[0]).toHaveTextContent('2 ×')
    expect(items[0]).toHaveTextContent(/100,00/)
    expect(items[0]).toHaveTextContent(/200,00/)
  })

  it('shows the total, customer data and the warehouse name for pickup', () => {
    render(<OrderSummary order={order} warehouseName="Depósito Centro" />)

    expect(screen.getByText('Total')).toBeInTheDocument()
    expect(screen.getByText(/250,00/)).toBeInTheDocument()
    expect(screen.getByText('Ana Pérez')).toBeInTheDocument()
    expect(screen.getByText('ana@example.com')).toBeInTheDocument()
    expect(screen.getByText('Calle 1')).toBeInTheDocument()
    expect(screen.getByText('Retiro en depósito: Depósito Centro')).toBeInTheDocument()
  })

  it('falls back to the warehouse id when the name is unknown', () => {
    render(<OrderSummary order={order} />)

    expect(screen.getByText('Retiro en depósito: WH-1')).toBeInTheDocument()
  })

  it('shows home delivery for shipping orders', () => {
    render(<OrderSummary order={{ ...order, delivery: { method: 'shipping' } }} />)

    expect(screen.getByText('Envío a domicilio')).toBeInTheDocument()
  })
})
