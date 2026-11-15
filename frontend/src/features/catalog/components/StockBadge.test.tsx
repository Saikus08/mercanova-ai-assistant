import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { StockBadge } from './StockBadge'

describe('StockBadge', () => {
  it.each([
    [0, 'Sin stock'],
    [1, 'Última unidad'],
    [3, 'Últimas 3 unidades'],
    [4, 'En stock'],
  ])('with %i units shows "%s"', (qty, text) => {
    render(<StockBadge availableQty={qty} />)

    expect(screen.getByText(text)).toBeInTheDocument()
  })
})
