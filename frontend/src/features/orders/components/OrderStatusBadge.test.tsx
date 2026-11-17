import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { OrderStatusBadge } from './OrderStatusBadge'

describe('OrderStatusBadge', () => {
  it.each([
    ['confirmed', 'Confirmada'],
    ['pending_confirmation', 'Pendiente de confirmación'],
    ['cancelled', 'Cancelada'],
  ] as const)('shows %s as "%s" and never the raw status', (status, label) => {
    render(<OrderStatusBadge status={status} />)

    expect(screen.getByText(label)).toBeInTheDocument()
    expect(screen.queryByText(status)).not.toBeInTheDocument()
  })
})
