import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiRequestError } from '../../api/http'
import type { OrdersApi } from '../../api/orders'
import type { Order } from '../../api/types'
import type { WarehousesApi } from '../../api/warehouses'
import { createFakeCartApi } from '../../test/fakeCartApi'
import { createFakeOrdersApi } from '../../test/fakeOrdersApi'
import { createFakeWarehousesApi } from '../../test/fakeWarehousesApi'
import { renderWithShop } from '../../test/renderWithShop'
import { CheckoutFlow } from './CheckoutFlow'

const ITEMS = { 'MN-MON-0001': 2, 'MN-HEA-0001': 1 }

interface SetupOptions {
  items?: Record<string, number>
  orders?: (base: OrdersApi) => Partial<OrdersApi>
  warehousesApi?: WarehousesApi
}

function setup({ items = ITEMS, orders = () => ({}), warehousesApi }: SetupOptions = {}) {
  const baseCart = createFakeCartApi(items)
  const getCart = vi.fn(baseCart.getCart)
  const cartApi = { ...baseCart, getCart }
  const base = createFakeOrdersApi(baseCart)
  const ordersApi: OrdersApi = {
    checkout: vi.fn(base.checkout),
    confirm: vi.fn(base.confirm),
    cancel: vi.fn(base.cancel),
    ...orders(base),
  }
  renderWithShop(<CheckoutFlow />, { cartApi, ordersApi, warehousesApi, path: '/checkout', route: '/checkout' })
  return { user: userEvent.setup(), ordersApi, getCart }
}

async function fillForm(user: ReturnType<typeof userEvent.setup>) {
  await user.type(await screen.findByRole('textbox', { name: /Nombre/ }), 'Ana Pérez')
  await user.type(screen.getByRole('textbox', { name: /Email/ }), 'ana@example.com')
  await user.type(screen.getByRole('textbox', { name: /Dirección/ }), 'Av. 18 de Julio 1234')
  await user.selectOptions(screen.getByRole('combobox', { name: 'Depósito de retiro' }), 'WH-MVD-CEN')
}

async function openDialog(user: ReturnType<typeof userEvent.setup>) {
  await fillForm(user)
  await user.click(screen.getByRole('button', { name: 'Revisar compra' }))
  return screen.findByRole('dialog', { name: 'Confirmá tu compra' })
}

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((r) => {
    resolve = r
  })
  return { promise, resolve }
}

describe('CheckoutFlow', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('goes from the form to the confirmation dialog to the purchase complete screen', async () => {
    const consoleSpies = (['log', 'info', 'warn', 'error', 'debug'] as const).map((method) =>
      vi.spyOn(console, method).mockImplementation(() => {}),
    )
    const { user, ordersApi, getCart } = setup()
    await fillForm(user)

    await user.click(screen.getByRole('button', { name: 'Revisar compra' }))

    expect(ordersApi.checkout).toHaveBeenCalledWith({
      customer: { name: 'Ana Pérez', email: 'ana@example.com', address: 'Av. 18 de Julio 1234' },
      delivery: { method: 'pickup', warehouse_id: 'WH-MVD-CEN' },
    })
    const dialog = await screen.findByRole('dialog', { name: 'Confirmá tu compra' })
    expect(within(dialog).getByText('Flux Vision 24 QHD IPS')).toBeInTheDocument()
    expect(within(dialog).getByText('Retiro en depósito: Depósito Centro')).toBeInTheDocument()
    expect(ordersApi.confirm).not.toHaveBeenCalled()

    const cartLoads = getCart.mock.calls.length
    await user.click(within(dialog).getByRole('button', { name: 'Confirmar compra' }))

    expect(await screen.findByRole('heading', { name: '¡Compra confirmada!' })).toBeInTheDocument()
    expect(screen.getByText('ORD-TEST-1')).toBeInTheDocument()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(ordersApi.confirm).toHaveBeenCalledOnce()
    expect(ordersApi.confirm).toHaveBeenCalledWith('ORD-TEST-1')
    await waitFor(() => expect(getCart.mock.calls.length).toBeGreaterThan(cartLoads))
    for (const spy of consoleSpies) expect(spy).not.toHaveBeenCalled()
  })

  it('never confirms without the explicit click', async () => {
    const { user, ordersApi } = setup()
    await openDialog(user)

    await user.keyboard('{Escape}')

    expect(ordersApi.confirm).not.toHaveBeenCalled()
  })

  it('cancels the pending order from the button and keeps the typed values', async () => {
    const { user, ordersApi } = setup()
    const dialog = await openDialog(user)

    await user.click(within(dialog).getByRole('button', { name: 'Cancelar compra' }))

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(ordersApi.cancel).toHaveBeenCalledWith('ORD-TEST-1')
    expect(ordersApi.confirm).not.toHaveBeenCalled()
    expect(screen.getByRole('textbox', { name: /Nombre/ })).toHaveValue('Ana Pérez')
    expect(screen.getByRole('textbox', { name: /Email/ })).toHaveValue('ana@example.com')
    expect(screen.getByRole('textbox', { name: /Dirección/ })).toHaveValue('Av. 18 de Julio 1234')
    expect(screen.getByRole('combobox', { name: 'Depósito de retiro' })).toHaveValue('WH-MVD-CEN')
  })

  it('treats Escape as cancelling the purchase', async () => {
    const { user, ordersApi } = setup()
    await openDialog(user)

    await user.keyboard('{Escape}')

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(ordersApi.cancel).toHaveBeenCalledWith('ORD-TEST-1')
  })

  it('validates in Spanish before calling the API', async () => {
    const { user, ordersApi } = setup()
    await user.click(await screen.findByRole('button', { name: 'Revisar compra' }))

    expect(screen.getByText('Ingresá tu nombre.')).toBeInTheDocument()
    expect(screen.getByText('Ingresá tu email.')).toBeInTheDocument()
    expect(screen.getByText('Ingresá tu dirección.')).toBeInTheDocument()
    expect(screen.getByText('Elegí un depósito para retirar.')).toBeInTheDocument()
    expect(ordersApi.checkout).not.toHaveBeenCalled()
  })

  it('maps a VALIDATION_ERROR to the form fields without showing the English text', async () => {
    const { user } = setup({
      orders: () => ({
        checkout: vi.fn().mockRejectedValue(
          new ApiRequestError('VALIDATION_ERROR', 'Hay datos inválidos.', 400, {
            errors: [
              { field: 'customer.email', message: 'value is not a valid email address' },
              { field: 'delivery.warehouse_id', message: 'warehouse does not allow pickup' },
            ],
          }),
        ),
      }),
    })
    await fillForm(user)

    await user.click(screen.getByRole('button', { name: 'Revisar compra' }))

    expect(await screen.findByRole('textbox', { name: /Email/ })).toHaveAccessibleDescription('Revisá este dato')
    expect(screen.getByRole('combobox', { name: 'Depósito de retiro' })).toHaveAccessibleDescription('Revisá este dato')
    expect(screen.getByRole('textbox', { name: /Nombre/ })).not.toHaveAccessibleDescription()
    expect(screen.queryByText(/not a valid email/)).not.toBeInTheDocument()
    expect(screen.queryByText(/does not allow pickup/)).not.toBeInTheDocument()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it.each([
    ['CART_EMPTY', 'Tu carrito está vacío.'],
    ['INSUFFICIENT_STOCK', 'No hay stock suficiente para Echo Calm ANC.'],
  ] as const)('shows the %s message with a link back to the cart', async (code, message) => {
    const { user } = setup({
      orders: () => ({ checkout: vi.fn().mockRejectedValue(new ApiRequestError(code, message, 409)) }),
    })
    await fillForm(user)

    await user.click(screen.getByRole('button', { name: 'Revisar compra' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(message)
    expect(screen.getByRole('link', { name: 'Volver al carrito' })).toHaveAttribute('href', '/cart')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('names the product and the available units when confirming fails for stock, and cancels the order', async () => {
    const { user, ordersApi } = setup({
      orders: () => ({
        confirm: vi.fn().mockRejectedValue(
          new ApiRequestError('INSUFFICIENT_STOCK', 'Insufficient stock', 409, {
            product_id: 'MN-HEA-0001',
            available_qty: 1,
          }),
        ),
      }),
    })
    const dialog = await openDialog(user)

    await user.click(within(dialog).getByRole('button', { name: 'Confirmar compra' }))

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Solo queda 1 unidad de Echo Calm ANC.')
    expect(screen.getByRole('link', { name: 'Volver al carrito' })).toHaveAttribute('href', '/cart')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(ordersApi.cancel).toHaveBeenCalledWith('ORD-TEST-1')
  })

  it('explains a price change and lets the user rebuild the order', async () => {
    const { user, ordersApi, getCart } = setup({
      orders: () => ({
        confirm: vi.fn().mockRejectedValue(
          new ApiRequestError('PRICE_CHANGED', 'El precio cambió.', 409, {
            product_id: 'MN-MON-0001',
            old_price: 100,
            new_price: 120,
          }),
        ),
      }),
    })
    const dialog = await openDialog(user)

    await user.click(within(dialog).getByRole('button', { name: 'Confirmar compra' }))

    const alert = await within(dialog).findByRole('alert')
    expect(alert).toHaveTextContent('El precio de Flux Vision 24 QHD IPS cambió de')
    expect(alert).toHaveTextContent(/100,00/)
    expect(alert).toHaveTextContent(/120,00/)
    expect(within(dialog).queryByRole('button', { name: 'Confirmar compra' })).not.toBeInTheDocument()

    const cartLoads = getCart.mock.calls.length
    await user.click(within(alert).getByRole('button', { name: 'Armar la orden de nuevo' }))

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(ordersApi.cancel).toHaveBeenCalledWith('ORD-TEST-1')
    await waitFor(() => expect(getCart.mock.calls.length).toBeGreaterThan(cartLoads))
    expect(screen.getByRole('textbox', { name: /Nombre/ })).toHaveValue('Ana Pérez')
  })

  it('closes the dialog with a way out when the order is no longer pending', async () => {
    const { user } = setup({
      orders: () => ({
        confirm: vi.fn().mockRejectedValue(new ApiRequestError('ORDER_NOT_PENDING', 'La orden ya no está pendiente.', 409)),
      }),
    })
    const dialog = await openDialog(user)

    await user.click(within(dialog).getByRole('button', { name: 'Confirmar compra' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('La orden ya no está pendiente.')
    expect(screen.getByRole('link', { name: 'Volver al carrito' })).toBeInTheDocument()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('keeps the dialog open with the message on a network error so the user can retry', async () => {
    const { user, ordersApi } = setup({
      orders: (base) => ({
        confirm: vi
          .fn()
          .mockRejectedValueOnce(new ApiRequestError('NETWORK_ERROR', 'No pudimos conectarnos con la tienda.', null))
          .mockImplementation(base.confirm),
      }),
    })
    const dialog = await openDialog(user)

    await user.click(within(dialog).getByRole('button', { name: 'Confirmar compra' }))

    expect(await within(dialog).findByRole('alert')).toHaveTextContent('No pudimos conectarnos con la tienda.')
    await user.click(within(dialog).getByRole('button', { name: 'Confirmar compra' }))

    expect(await screen.findByRole('heading', { name: '¡Compra confirmada!' })).toBeInTheDocument()
    expect(ordersApi.confirm).toHaveBeenCalledTimes(2)
  })

  it('sends one confirm request when the button is clicked twice', async () => {
    const pending = deferred<Order>()
    const { user, ordersApi } = setup({ orders: () => ({ confirm: vi.fn().mockReturnValue(pending.promise) }) })
    const dialog = await openDialog(user)

    await user.dblClick(within(dialog).getByRole('button', { name: 'Confirmar compra' }))

    expect(ordersApi.confirm).toHaveBeenCalledOnce()
    expect(within(dialog).getByRole('button', { name: 'Cancelar compra' })).toBeDisabled()
    expect(within(dialog).getByRole('button', { name: 'Confirmar compra' })).toBeDisabled()
  })

  it('sends one checkout request when "Revisar compra" is clicked twice', async () => {
    const pending = deferred<Order>()
    const { user, ordersApi } = setup({ orders: () => ({ checkout: vi.fn().mockReturnValue(pending.promise) }) })
    await fillForm(user)

    await user.dblClick(screen.getByRole('button', { name: 'Revisar compra' }))

    expect(ordersApi.checkout).toHaveBeenCalledOnce()
  })

  it('shows the empty cart instead of the form', async () => {
    setup({ items: {} })

    expect(await screen.findByText('Tu carrito está vacío')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Ver el catálogo' })).toHaveAttribute('href', '/')
    expect(screen.queryByRole('button', { name: 'Revisar compra' })).not.toBeInTheDocument()
  })

  it('shows a loading state and then a retryable error when warehouses fail to load', async () => {
    const base = createFakeWarehousesApi()
    const listWarehouses = vi
      .fn<WarehousesApi['listWarehouses']>()
      .mockRejectedValueOnce(new ApiRequestError('NETWORK_ERROR', 'Sin conexión.', null))
      .mockImplementation(base.listWarehouses)
    const { user } = setup({ warehousesApi: { listWarehouses } })

    expect(screen.getByText('Cargando…')).toBeInTheDocument()
    expect(await screen.findByRole('alert')).toHaveTextContent('Sin conexión.')

    await user.click(screen.getByRole('button', { name: 'Reintentar' }))

    expect(await screen.findByRole('button', { name: 'Revisar compra' })).toBeInTheDocument()
  })
})
