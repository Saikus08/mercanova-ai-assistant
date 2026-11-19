import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { ToolsUsedPanel } from './ToolsUsedPanel'

describe('ToolsUsedPanel', () => {
  it('lists the tools in order with their arguments inside "Cómo lo resolví"', async () => {
    const user = userEvent.setup()
    render(
      <ToolsUsedPanel
        tools={[
          { name: 'search_products', args: { query: 'noise cancelling headphones', max_price: 200 } },
          { name: 'get_stock', args: { product_id: 'MN-HEA-0001' } },
        ]}
      />,
    )

    await user.click(screen.getByText('Cómo lo resolví'))

    const items = screen.getAllByRole('listitem')
    expect(items[0]).toHaveTextContent('Buscó productos en el catálogo')
    expect(items[0]).toHaveTextContent('noise cancelling headphones')
    expect(items[0]).toHaveTextContent('200')
    expect(items[1]).toHaveTextContent('Consultó el stock actual')
  })

  it('renders nothing when no tool was used', () => {
    const { container } = render(<ToolsUsedPanel tools={[]} />)

    expect(container).toBeEmptyDOMElement()
  })
})
