import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { confirmedOrder, pendingOrder } from '../../../test/orderFixtures'
import { OrderDetailView } from './OrderDetailView'

describe('OrderDetailView', () => {
  it('shows the order id, the status and the creation date', () => {
    render(<OrderDetailView order={pendingOrder} />)

    expect(screen.getByRole('heading', { level: 1, name: /ORD-20261112-0001/ })).toBeInTheDocument()
    expect(screen.getByText('Pendiente de confirmación')).toBeInTheDocument()
    expect(screen.getByText('12/11/2026, 19:00')).toBeInTheDocument()
  })

  it('shows the confirmation date only when the order has one', () => {
    const { rerender } = render(<OrderDetailView order={pendingOrder} />)
    expect(screen.queryByText('Confirmada el')).not.toBeInTheDocument()

    rerender(<OrderDetailView order={confirmedOrder} />)
    expect(screen.getByText('Confirmada el')).toBeInTheDocument()
    expect(screen.getByText('12/11/2026, 19:05')).toBeInTheDocument()
  })

  it('shows pickup with the warehouse id, or shipping', () => {
    const { rerender } = render(<OrderDetailView order={confirmedOrder} />)
    expect(screen.getByText('Retiro en depósito: WH-MVD-CEN')).toBeInTheDocument()

    rerender(<OrderDetailView order={pendingOrder} />)
    expect(screen.getByText('Envío a domicilio')).toBeInTheDocument()
  })

  it('shows the customer data, the prices paid and the total', () => {
    render(<OrderDetailView order={confirmedOrder} />)

    expect(screen.getByText('Ana Pérez')).toBeInTheDocument()
    expect(screen.getByText('ana@example.com')).toBeInTheDocument()
    expect(screen.getByText('Calle 1 123')).toBeInTheDocument()
    expect(screen.getByText('Flux Vision 24')).toBeInTheDocument()
    expect(screen.getByText(/2 × .*100,00/)).toBeInTheDocument()
    expect(screen.getByText(/250,00/)).toBeInTheDocument()
  })
})
