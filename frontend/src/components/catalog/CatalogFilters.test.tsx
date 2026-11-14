import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { mockCategories } from '../../api/mocks/catalogData'
import { CatalogFilters } from './CatalogFilters'

describe('CatalogFilters', () => {
  it('offers only the subcategories of the selected category', () => {
    render(
      <CatalogFilters value={{ category: 'Monitors' }} categories={mockCategories} onChange={vi.fn()} onClear={vi.fn()} />,
    )

    const options = within(screen.getByLabelText('Subcategoría')).getAllByRole('option')
    expect(options.map((o) => o.textContent)).toEqual(['Todas', 'Gaming', 'Office'])
  })

  it('clears the subcategory when the category changes', async () => {
    const onChange = vi.fn()
    render(
      <CatalogFilters
        value={{ category: 'Monitors', subcategory: 'Gaming' }}
        categories={mockCategories}
        onChange={onChange}
        onClear={vi.fn()}
      />,
    )

    await userEvent.selectOptions(screen.getByLabelText('Categoría'), 'Laptops')

    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ category: 'Laptops', subcategory: undefined }),
    )
  })

  it('sends the price range on submit', async () => {
    const onChange = vi.fn()
    render(<CatalogFilters value={{}} categories={mockCategories} onChange={onChange} onClear={vi.fn()} />)

    await userEvent.type(screen.getByLabelText('Mínimo'), '100')
    await userEvent.type(screen.getByLabelText('Máximo'), '300')
    await userEvent.click(screen.getByRole('button', { name: 'Aplicar' }))

    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ min_price: 100, max_price: 300 }))
  })

  it('blocks a minimum price higher than the maximum', async () => {
    const onChange = vi.fn()
    render(<CatalogFilters value={{}} categories={mockCategories} onChange={onChange} onClear={vi.fn()} />)

    await userEvent.type(screen.getByLabelText('Mínimo'), '500')
    await userEvent.type(screen.getByLabelText('Máximo'), '100')

    expect(screen.getByLabelText('Máximo')).toHaveAccessibleDescription('Tiene que ser mayor que el mínimo.')
    expect(screen.getByRole('button', { name: 'Aplicar' })).toBeDisabled()
    expect(onChange).not.toHaveBeenCalled()
  })
})
