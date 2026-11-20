import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { OrdersApi } from '../api/orders'
import { App } from '../App'
import { createFakeCartApi } from '../test/fakeCartApi'
import { answerEvents, createFakeChatApi } from '../test/fakeChatApi'
import { createFakeOrdersApi } from '../test/fakeOrdersApi'
import { renderWithShop } from '../test/renderWithShop'

/** "Comprámelo" (use case 10): the assistant only prepares the draft; the user confirms in the checkout screen. */
async function setup() {
  const cartApi = createFakeCartApi({ 'MN-HEA-0001': 1 })
  const base = createFakeOrdersApi(cartApi)
  const ordersApi: OrdersApi = { ...base, checkout: vi.fn(base.checkout), confirm: vi.fn(base.confirm) }
  const chatApi = createFakeChatApi([
    answerEvents('Tu compra está lista para revisar.', {
      tools: [{ name: 'start_checkout', args: {} }],
      blocks: [{ type: 'checkout_draft', cart: await cartApi.getCart() }],
    }),
  ])
  renderWithShop(<App />, { cartApi, ordersApi, chatApi, path: '/chat', route: '/*' })
  return { user: userEvent.setup(), ordersApi, chatApi }
}

async function askToBuy(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText('¿Qué estás buscando?'), 'Comprámelo')
  await user.click(screen.getByRole('button', { name: 'Enviar' }))
  return screen.findByRole('button', { name: 'Revisar y confirmar la compra' })
}

describe('chat to checkout flow', () => {
  it('registers nothing when the assistant prepares the purchase', async () => {
    const { user, ordersApi } = await setup()

    await askToBuy(user)

    expect(screen.getByTestId('location')).toHaveTextContent('/chat')
    expect(ordersApi.checkout).not.toHaveBeenCalled()
    expect(ordersApi.confirm).not.toHaveBeenCalled()
  })

  it('goes from the checkout draft to the form, the dialog and the confirmed purchase', async () => {
    const { user, ordersApi, chatApi } = await setup()
    await user.click(await askToBuy(user))

    expect(screen.getByTestId('location')).toHaveTextContent('/checkout')
    await user.type(await screen.findByRole('textbox', { name: /Nombre/ }), 'Ana Pérez')
    await user.type(screen.getByRole('textbox', { name: /Email/ }), 'ana@example.com')
    await user.type(screen.getByRole('textbox', { name: /Dirección/ }), 'Av. 18 de Julio 1234')
    await user.selectOptions(screen.getByRole('combobox', { name: 'Depósito de retiro' }), 'WH-MVD-CEN')
    await user.click(screen.getByRole('button', { name: 'Revisar compra' }))

    const dialog = await screen.findByRole('dialog', { name: 'Confirmá tu compra' })
    expect(within(dialog).getByText('Echo Calm ANC')).toBeInTheDocument()
    expect(ordersApi.confirm).not.toHaveBeenCalled()

    await user.click(within(dialog).getByRole('button', { name: 'Confirmar compra' }))

    expect(await screen.findByRole('heading', { name: '¡Compra confirmada!' })).toBeInTheDocument()
    expect(ordersApi.confirm).toHaveBeenCalledExactlyOnceWith('ORD-TEST-1')
    // Personal data goes to the checkout API only, never to the assistant.
    expect(JSON.stringify(chatApi.requests)).not.toMatch(/Ana Pérez|ana@example\.com|18 de Julio/)
  })

  it('keeps the conversation when the user comes back from the checkout screen', async () => {
    const { user } = await setup()
    await user.click(await askToBuy(user))
    expect(screen.getByTestId('location')).toHaveTextContent('/checkout')

    await user.click(screen.getByRole('link', { name: 'Asistente' }))

    const log = screen.getByRole('log', { name: 'Conversación' })
    expect(within(log).getByText('Comprámelo')).toBeInTheDocument()
    expect(within(log).getByText('Tu compra está lista para revisar.')).toBeInTheDocument()
  })
})
