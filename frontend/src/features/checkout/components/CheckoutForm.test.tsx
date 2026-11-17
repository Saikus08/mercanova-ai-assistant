import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { fakeWarehouses } from '../../../test/fakeWarehousesApi'
import type { CheckoutFormErrors, CheckoutFormValues } from '../checkoutForm'
import { CheckoutForm } from './CheckoutForm'

const empty: CheckoutFormValues = { name: '', email: '', address: '', method: 'pickup', warehouseId: '' }

interface HarnessProps {
  initial?: CheckoutFormValues
  warehouses?: typeof fakeWarehouses
  errors?: CheckoutFormErrors
  submitting?: boolean
  onSubmit?: () => void
}

/** The form is controlled, so tests that type need a parent holding the values. */
function Harness({ initial = empty, warehouses = fakeWarehouses, errors = {}, submitting = false, onSubmit = vi.fn() }: HarnessProps) {
  const [values, setValues] = useState(initial)
  return (
    <CheckoutForm
      values={values}
      warehouses={warehouses}
      errors={errors}
      submitting={submitting}
      onChange={setValues}
      onSubmit={onSubmit}
    />
  )
}

describe('CheckoutForm', () => {
  it('has labelled name, email and address fields and no payment fields', () => {
    render(<Harness />)

    expect(screen.getByRole('textbox', { name: /Nombre/ })).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: /Email/ })).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: /Dirección/ })).toBeInTheDocument()
    expect(screen.getAllByRole('textbox')).toHaveLength(3)
    expect(screen.queryByLabelText(/tarjeta|cvv|vencimiento/i)).not.toBeInTheDocument()
  })

  it('updates the values while typing', async () => {
    const user = userEvent.setup()
    render(<Harness />)

    await user.type(screen.getByRole('textbox', { name: /Nombre/ }), 'Ana')

    expect(screen.getByRole('textbox', { name: /Nombre/ })).toHaveValue('Ana')
  })

  it('offers only warehouses with pickup enabled', () => {
    render(<Harness />)

    const select = screen.getByRole('combobox', { name: 'Depósito de retiro' })
    const options = within(select).getAllByRole('option').map((option) => option.textContent)
    expect(options).toEqual(['Elegí un depósito', 'Depósito Centro (Montevideo)', 'Depósito Canelones (Las Piedras)'])
  })

  it('offers home delivery only when some warehouse ships', async () => {
    const user = userEvent.setup()
    const { unmount } = render(<Harness />)
    expect(screen.getByRole('radio', { name: 'Envío a domicilio' })).toBeInTheDocument()
    await user.click(screen.getByRole('radio', { name: 'Envío a domicilio' }))
    expect(screen.queryByRole('combobox', { name: 'Depósito de retiro' })).not.toBeInTheDocument()
    unmount()

    render(<Harness warehouses={fakeWarehouses.map((w) => ({ ...w, shipping_enabled: false }))} />)
    expect(screen.queryByRole('radio', { name: 'Envío a domicilio' })).not.toBeInTheDocument()
    expect(screen.getByRole('radio', { name: 'Retiro en depósito' })).toBeChecked()
  })

  it('shows the error of each field', () => {
    render(
      <Harness
        errors={{ name: 'Ingresá tu nombre.', email: 'Ingresá un email válido.', address: 'Revisá este dato', warehouse: 'Elegí un depósito para retirar.' }}
      />,
    )

    expect(screen.getByRole('textbox', { name: /Nombre/ })).toHaveAccessibleDescription('Ingresá tu nombre.')
    expect(screen.getByRole('textbox', { name: /Email/ })).toHaveAccessibleDescription('Ingresá un email válido.')
    expect(screen.getByRole('textbox', { name: /Dirección/ })).toHaveAccessibleDescription('Revisá este dato')
    expect(screen.getByRole('combobox', { name: 'Depósito de retiro' })).toHaveAccessibleDescription(
      'Elegí un depósito para retirar.',
    )
  })

  it('submits through the "Revisar compra" button', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    render(<Harness onSubmit={onSubmit} />)

    await user.click(screen.getByRole('button', { name: 'Revisar compra' }))

    expect(onSubmit).toHaveBeenCalledOnce()
  })

  it('disables the submit button while submitting', () => {
    render(<Harness submitting />)

    expect(screen.getByRole('button', { name: /Revisar compra/ })).toBeDisabled()
  })

  it('tells the user when no delivery option exists', () => {
    render(<Harness warehouses={[]} />)

    expect(screen.getByText('Por ahora no hay opciones de entrega disponibles.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Revisar compra' })).toBeDisabled()
  })
})
