import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { AddToCartButton } from './AddToCartButton'

describe('AddToCartButton', () => {
  it('calls onAdd when clicked', async () => {
    const onAdd = vi.fn()
    render(<AddToCartButton onAdd={onAdd} />)

    await userEvent.click(screen.getByRole('button', { name: 'Agregar al carrito' }))

    expect(onAdd).toHaveBeenCalledOnce()
  })

  it('shows "Sin stock" and cannot be clicked when out of stock', () => {
    render(<AddToCartButton onAdd={() => {}} outOfStock />)

    expect(screen.getByRole('button', { name: 'Sin stock' })).toBeDisabled()
  })

  it('blocks clicks while pending', () => {
    render(<AddToCartButton onAdd={() => {}} pending />)

    expect(screen.getByRole('button')).toBeDisabled()
  })

  it('accepts a custom label and disabled state', () => {
    render(<AddToCartButton onAdd={() => {}} label="Sumar" disabled />)

    expect(screen.getByRole('button', { name: 'Sumar' })).toBeDisabled()
  })
})
