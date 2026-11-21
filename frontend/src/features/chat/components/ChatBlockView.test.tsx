import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { describe, expect, it, vi } from 'vitest'
import type { Cart, ChatBlock } from '../../../api/types'
import { chatProduct } from '../../../test/fakeChatApi'
import { ChatBlockView } from './ChatBlockView'

const cart: Cart = {
  items: [
    { product_id: 'MN-HEA-0001', name: 'Echo Calm ANC', image_url: null, unit_price: 50, quantity: 2, line_total: 100, available_qty: 2 },
  ],
  item_count: 2,
  total: 100,
  currency: 'USD',
}

function renderBlock(block: ChatBlock, props: Partial<Parameters<typeof ChatBlockView>[0]> = {}) {
  const handlers = { onSelectOption: vi.fn(), onCheckout: vi.fn() }
  render(
    <MemoryRouter>
      <ChatBlockView block={block} {...handlers} {...props} />
    </MemoryRouter>,
  )
  return handlers
}

describe('ChatBlockView', () => {
  it('shows product recommendations with the reason, price, stock and the container actions', () => {
    renderBlock(
      { type: 'product_recommendations', items: [{ product: chatProduct(), reason: 'Tiene cancelación de ruido.' }] },
      { renderProductActions: (product) => <button type="button">Agregar {product.name}</button> },
    )

    const list = screen.getByRole('list', { name: 'Productos recomendados' })
    expect(within(list).getByRole('link', { name: 'Echo Calm ANC' })).toHaveAttribute('href', '/products/MN-HEA-0001')
    expect(within(list).getByText('Tiene cancelación de ruido.')).toBeInTheDocument()
    expect(within(list).getByText(/50,00/)).toBeInTheDocument()
    expect(within(list).getByText('Últimas 2 unidades')).toBeInTheDocument()
    expect(within(list).getByRole('button', { name: 'Agregar Echo Calm ANC' })).toBeInTheDocument()
  })

  it('renders a recommendation without image or rating', () => {
    renderBlock({
      type: 'product_recommendations',
      items: [{ product: chatProduct({ image_url: null, rating: null, review_count: null }), reason: 'Barato.' }],
    })

    expect(screen.queryByRole('img')).not.toBeInTheDocument()
    expect(screen.queryByText(/opiniones/)).not.toBeInTheDocument()
  })

  it('shows the comparison as a table with price, stock and attributes', () => {
    renderBlock({
      type: 'comparison',
      products: [chatProduct(), chatProduct({ product_id: 'MN-HEA-0002', name: 'Echo Pro', available_qty: 0 })],
      attributes: [
        { group: 'Audio', name: 'Battery', unit: 'h', values: { 'MN-HEA-0001': '30', 'MN-HEA-0002': null } },
      ],
    })

    const table = screen.getByRole('table', { name: 'Comparación de productos' })
    expect(within(table).getByRole('columnheader', { name: /Echo Pro/ })).toBeInTheDocument()
    const battery = within(table).getByRole('row', { name: /Battery/ })
    expect(within(battery).getByText('30 h')).toBeInTheDocument()
    expect(within(battery).getByText('—')).toBeInTheDocument()
    expect(within(within(table).getByRole('row', { name: /Stock/ })).getByText('Sin stock')).toBeInTheDocument()
  })

  it('names the corner cell of the comparison for screen readers', () => {
    renderBlock({ type: 'comparison', products: [chatProduct(), chatProduct({ product_id: 'MN-HEA-0002' })], attributes: [] })

    const headers = within(screen.getByRole('table')).getAllByRole('columnheader')
    expect(headers[0]).toHaveAccessibleName('Característica')
  })

  it('sends a quick reply when an option is clicked', async () => {
    const user = userEvent.setup()
    const { onSelectOption } = renderBlock({
      type: 'clarification',
      question: '¿Para qué lo vas a usar?',
      options: ['Trabajo', 'Gaming'],
    })

    expect(screen.getByText('¿Para qué lo vas a usar?')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Gaming' }))

    expect(onSelectOption).toHaveBeenCalledWith('Gaming')
  })

  it('disables the quick replies of older answers', () => {
    renderBlock({ type: 'clarification', question: '¿Para qué?', options: ['Trabajo'] }, { optionsDisabled: true })

    expect(screen.getByRole('button', { name: 'Trabajo' })).toBeDisabled()
  })

  it('shows the cart update with a link to the cart', () => {
    renderBlock({ type: 'cart_updated', cart })

    expect(screen.getByText(/Carrito actualizado: 2 productos/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Ver carrito' })).toHaveAttribute('href', '/cart')
  })

  it('shows the checkout summary and only opens the checkout when clicked', async () => {
    const user = userEvent.setup()
    const { onCheckout } = renderBlock({ type: 'checkout_draft', cart })

    expect(within(screen.getByRole('list', { name: 'Resumen de la compra' })).getByText('2 × Echo Calm ANC')).toBeInTheDocument()
    expect(onCheckout).not.toHaveBeenCalled()
    await user.click(screen.getByRole('button', { name: 'Revisar y confirmar la compra' }))

    expect(onCheckout).toHaveBeenCalledTimes(1)
  })

  it('says when the product is not in the catalog', () => {
    renderBlock({ type: 'not_found', query: 'PlayStation 9' })

    expect(screen.getByText('No encontramos «PlayStation 9» en el catálogo de MercaNova.')).toBeInTheDocument()
  })
})
