import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { CartSummary } from './CartSummary'

describe('CartSummary', () => {
  it('shows the item count, the total and starts the checkout', async () => {
    const onCheckout = vi.fn()
    render(<CartSummary itemCount={3} total={250} currency="USD" onCheckout={onCheckout} />)

    expect(screen.getByText('3 productos')).toBeInTheDocument()
    expect(screen.getByText(/250,00/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Continuar con la compra' }))
    expect(onCheckout).toHaveBeenCalledOnce()
  })

  it('uses the singular for one product', () => {
    render(<CartSummary itemCount={1} total={10} currency="USD" onCheckout={() => {}} />)

    expect(screen.getByText('1 producto')).toBeInTheDocument()
  })

  it('disables the checkout button when the cart is empty', () => {
    render(<CartSummary itemCount={0} total={0} currency="USD" onCheckout={() => {}} />)

    expect(screen.getByRole('button', { name: 'Continuar con la compra' })).toBeDisabled()
  })
})
