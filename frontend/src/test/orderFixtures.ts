import type { Order } from '../api/types'

export const confirmedOrder: Order = {
  order_id: 'ORD-20261112-0002',
  status: 'confirmed',
  created_at: '2026-11-12T22:00:00Z',
  confirmed_at: '2026-11-12T22:05:00Z',
  customer: { name: 'Ana Pérez', email: 'ana@example.com', address: 'Calle 1 123' },
  delivery: { method: 'pickup', warehouse_id: 'WH-MVD-CEN' },
  items: [
    { product_id: 'P1', name: 'Flux Vision 24', unit_price: 100, quantity: 2, line_total: 200 },
    { product_id: 'P2', name: 'Echo Calm ANC', unit_price: 50, quantity: 1, line_total: 50 },
  ],
  total: 250,
  currency: 'USD',
}

export const pendingOrder: Order = {
  ...confirmedOrder,
  order_id: 'ORD-20261112-0001',
  status: 'pending_confirmation',
  confirmed_at: null,
  delivery: { method: 'shipping' },
  items: [confirmedOrder.items[0]],
  total: 200,
}

export const cancelledOrder: Order = {
  ...pendingOrder,
  order_id: 'ORD-20261111-0007',
  status: 'cancelled',
}
