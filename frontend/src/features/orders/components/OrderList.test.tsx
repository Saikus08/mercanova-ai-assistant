import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'
import { cancelledOrder, confirmedOrder, pendingOrder } from '../../../test/orderFixtures'
import { OrderList } from './OrderList'

function renderList() {
  return render(
    <MemoryRouter>
      <OrderList orders={[confirmedOrder, pendingOrder, cancelledOrder]} />
    </MemoryRouter>,
  )
}

describe('OrderList', () => {
  it('renders one row per order in the given order', () => {
    renderList()

    const rows = within(screen.getByRole('list', { name: 'Mis compras' })).getAllByRole('listitem')
    expect(rows).toHaveLength(3)
    expect(rows[0]).toHaveTextContent('ORD-20261112-0002')
    expect(rows[2]).toHaveTextContent('ORD-20261111-0007')
  })

  it('links each order id to its detail', () => {
    renderList()

    expect(screen.getByRole('link', { name: 'ORD-20261112-0002' })).toHaveAttribute('href', '/orders/ORD-20261112-0002')
  })

  it('shows the formatted date, status, item count and total', () => {
    renderList()

    const row = screen.getAllByRole('listitem')[0]
    expect(row).toHaveTextContent('12/11/2026, 19:00')
    expect(within(row).getByText('Confirmada')).toBeInTheDocument()
    expect(row).toHaveTextContent('3 productos')
    expect(row).toHaveTextContent(/250,00/)
    expect(screen.getAllByRole('listitem')[1]).toHaveTextContent('2 productos')
  })

  it('uses the singular for one product', () => {
    render(
      <MemoryRouter>
        <OrderList orders={[{ ...pendingOrder, items: [{ ...pendingOrder.items[0], quantity: 1 }] }]} />
      </MemoryRouter>,
    )

    expect(screen.getByRole('listitem')).toHaveTextContent('1 producto')
    expect(screen.getByRole('listitem')).not.toHaveTextContent('1 productos')
  })
})
