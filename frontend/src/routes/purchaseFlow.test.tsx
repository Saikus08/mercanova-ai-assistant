import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { OrdersApi } from '../api/orders'
import { App } from '../App'
import { createFakeCartApi } from '../test/fakeCartApi'
import { createFakeOrdersApi } from '../test/fakeOrdersApi'
import { renderWithShop } from '../test/renderWithShop'

const PRODUCT = 'Flux Vision 24 QHD IPS'

/** The main purchase flow (RF-09, RF-12) through the whole app: search, cart, checkout, confirmation. */
function setup() {
  const cartApi = createFakeCartApi()
  const base = createFakeOrdersApi(cartApi)
  const ordersApi: OrdersApi = { ...base, checkout: vi.fn(base.checkout), confirm: vi.fn(base.confirm) }
  renderWithShop(<App />, { cartApi, ordersApi, path: '/', route: '/*' })
  return { user: userEvent.setup(), ordersApi }
}

type User = ReturnType<typeof userEvent.setup>

async function searchAndAdd(user: User) {
  await screen.findByRole('list', { name: 'Productos' })
  await user.type(screen.getByLabelText('Buscar'), 'flux{Enter}')
  await screen.findByTestId('location').then((probe) => expect(probe).toHaveTextContent('/?q=flux'))
  await user.click(await screen.findByRole('button', { name: `Agregar al carrito: ${PRODUCT}` }))
  expect(await screen.findByText('Agregado al carrito')).toBeInTheDocument()
}

async function openConfirmation(user: User) {
  await user.click(await screen.findByRole('link', { name: 'Carrito, 1 producto' }))
  const line = await screen.findByRole('article', { name: PRODUCT })
  await user.click(within(line).getByRole('button', { name: `Agregar una unidad de ${PRODUCT}` }))
  expect(await screen.findByRole('link', { name: 'Carrito, 2 productos' })).toBeInTheDocument()

  await user.click(screen.getByRole('button', { name: 'Continuar con la compra' }))
  await user.type(await screen.findByRole('textbox', { name: /Nombre/ }), 'Ana Pérez')
  await user.type(screen.getByRole('textbox', { name: /Email/ }), 'ana@example.com')
  await user.type(screen.getByRole('textbox', { name: /Dirección/ }), 'Av. 18 de Julio 1234')
  await user.selectOptions(screen.getByRole('combobox', { name: 'Depósito de retiro' }), 'WH-MVD-CEN')
  await user.click(screen.getByRole('button', { name: 'Revisar compra' }))
  return screen.findByRole('dialog', { name: 'Confirmá tu compra' })
}

describe('purchase flow', () => {
  it('searches, adds to the cart, changes the quantity and confirms the purchase', async () => {
    const { user, ordersApi } = setup()
    await searchAndAdd(user)

    const dialog = await openConfirmation(user)

    expect(within(dialog).getByText(PRODUCT)).toBeInTheDocument()
    expect(ordersApi.checkout).toHaveBeenCalledOnce()
    expect(ordersApi.confirm).not.toHaveBeenCalled()

    await user.click(within(dialog).getByRole('button', { name: 'Confirmar compra' }))

    expect(await screen.findByRole('heading', { name: '¡Compra confirmada!' })).toBeInTheDocument()
    expect(ordersApi.confirm).toHaveBeenCalledExactlyOnceWith('ORD-TEST-1')
    // Confirming empties the cart on the server, and the header reads it again.
    expect(await screen.findByRole('link', { name: 'Carrito' })).toBeInTheDocument()

    await user.click(screen.getByRole('link', { name: 'Ver mis compras' }))

    const orders = await screen.findByRole('list', { name: 'Mis compras' })
    expect(within(orders).getByRole('link', { name: 'ORD-TEST-1' })).toBeInTheDocument()
  })

  it('registers nothing and keeps the cart when the purchase is cancelled in the dialog', async () => {
    const { user, ordersApi } = setup()
    await searchAndAdd(user)
    const dialog = await openConfirmation(user)

    await user.click(within(dialog).getByRole('button', { name: 'Cancelar compra' }))

    expect(await screen.findByRole('heading', { level: 1, name: 'Finalizar compra' })).toBeInTheDocument()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(ordersApi.confirm).not.toHaveBeenCalled()
    expect(screen.getByRole('link', { name: 'Carrito, 2 productos' })).toBeInTheDocument()
  })
})
