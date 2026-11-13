import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { Input } from './Input'

describe('Input', () => {
  it('associates the visible label with the field', async () => {
    render(<Input label="Email" />)

    const field = screen.getByLabelText('Email')
    expect(field.tagName).toBe('INPUT')

    await userEvent.type(field, 'ana@example.com')
    expect(field).toHaveValue('ana@example.com')
  })

  it('shows the error message and marks the field invalid', () => {
    render(<Input label="Email" error="Ingresá un email válido." />)

    const field = screen.getByLabelText('Email')
    expect(field).toHaveAttribute('aria-invalid', 'true')
    expect(field).toHaveAccessibleDescription('Ingresá un email válido.')
    expect(screen.getByText('Ingresá un email válido.')).toBeVisible()
  })

  it('is not marked invalid without an error', () => {
    render(<Input label="Nombre" hint="Como figura en tu documento." />)

    const field = screen.getByLabelText('Nombre')
    expect(field).not.toHaveAttribute('aria-invalid')
    expect(field).toHaveAccessibleDescription('Como figura en tu documento.')
  })
})
