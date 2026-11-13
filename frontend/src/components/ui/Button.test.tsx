import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { Button } from './Button'

describe('Button', () => {
  it('renders its label as a button', () => {
    render(<Button>Agregar al carrito</Button>)

    const button = screen.getByRole('button', { name: 'Agregar al carrito' })
    expect(button).toBeInTheDocument()
    expect(button).toHaveAttribute('type', 'button')
  })

  it('calls onClick when clicked', async () => {
    const onClick = vi.fn()
    render(<Button onClick={onClick}>Comprar</Button>)

    await userEvent.click(screen.getByRole('button', { name: 'Comprar' }))

    expect(onClick).toHaveBeenCalledTimes(1)
  })

  it('does not call onClick when disabled', async () => {
    const onClick = vi.fn()
    render(
      <Button onClick={onClick} disabled>
        Comprar
      </Button>,
    )

    const button = screen.getByRole('button', { name: 'Comprar' })
    await userEvent.click(button)

    expect(button).toBeDisabled()
    expect(onClick).not.toHaveBeenCalled()
  })

  it('is disabled and busy while loading', async () => {
    const onClick = vi.fn()
    render(
      <Button onClick={onClick} loading>
        Guardar
      </Button>,
    )

    const button = screen.getByRole('button', { name: /Guardar/ })
    await userEvent.click(button)

    expect(button).toBeDisabled()
    expect(button).toHaveAttribute('aria-busy', 'true')
    expect(screen.getByRole('status')).toHaveTextContent('Procesando…')
    expect(onClick).not.toHaveBeenCalled()
  })
})
