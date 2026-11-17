import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { Order } from '../../../api/types'
import { ConfirmOrderDialog, type ConfirmOrderDialogProps } from './ConfirmOrderDialog'

const order: Order = {
  order_id: 'ORD-1',
  status: 'pending_confirmation',
  created_at: '2026-11-12T22:00:00Z',
  confirmed_at: null,
  customer: { name: 'Ana Pérez', email: 'ana@example.com', address: 'Calle 1' },
  delivery: { method: 'shipping' },
  items: [{ product_id: 'P1', name: 'Flux Vision 24', unit_price: 100, quantity: 2, line_total: 200 }],
  total: 200,
  currency: 'USD',
}

function setup(props: Partial<ConfirmOrderDialogProps> = {}) {
  const onConfirm = vi.fn()
  const onCancel = vi.fn()
  render(<ConfirmOrderDialog order={order} pending={false} onConfirm={onConfirm} onCancel={onCancel} {...props} />)
  return { onConfirm, onCancel, user: userEvent.setup() }
}

describe('ConfirmOrderDialog', () => {
  it('shows the title, the order summary and both buttons', () => {
    setup()

    expect(screen.getByRole('dialog', { name: 'Confirmá tu compra' })).toBeInTheDocument()
    expect(screen.getByText('Flux Vision 24')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Confirmar compra' })).toBeEnabled()
    expect(screen.getByRole('button', { name: 'Cancelar compra' })).toBeEnabled()
  })

  it('calls onConfirm and onCancel from their buttons', async () => {
    const { onConfirm, onCancel, user } = setup()

    await user.click(screen.getByRole('button', { name: 'Confirmar compra' }))
    expect(onConfirm).toHaveBeenCalledOnce()
    expect(onCancel).not.toHaveBeenCalled()

    await user.click(screen.getByRole('button', { name: 'Cancelar compra' }))
    expect(onCancel).toHaveBeenCalledOnce()
  })

  it('treats Escape as "Cancelar compra"', async () => {
    const { onCancel, user } = setup()

    await user.keyboard('{Escape}')

    expect(onCancel).toHaveBeenCalledOnce()
  })

  it('does not close when the backdrop is clicked', async () => {
    const { onCancel, user } = setup()

    await user.click(screen.getByRole('dialog').parentElement!)

    expect(onCancel).not.toHaveBeenCalled()
  })

  it('disables both buttons and ignores Escape while a request is in flight', async () => {
    const { onCancel, onConfirm, user } = setup({ pending: true })

    expect(screen.getByRole('button', { name: /Confirmar compra/ })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Cancelar compra' })).toBeDisabled()

    await user.keyboard('{Escape}')
    await user.click(screen.getByRole('button', { name: 'Cerrar' }))

    expect(onCancel).not.toHaveBeenCalled()
    expect(onConfirm).not.toHaveBeenCalled()
  })

  it('renders the problem in an alert region', () => {
    setup({ problem: 'No pudimos conectarnos con la tienda.' })

    expect(screen.getByRole('alert')).toHaveTextContent('No pudimos conectarnos con la tienda.')
  })

  it('hides the confirm button when the order cannot be confirmed', () => {
    setup({ canConfirm: false })

    expect(screen.queryByRole('button', { name: 'Confirmar compra' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Cancelar compra' })).toBeInTheDocument()
  })
})
