import { useRef, useState } from 'react'
import { Link } from 'react-router'
import { ApiRequestError } from '../../api/http'
import type { Order, Warehouse } from '../../api/types'
import { Button, Card, Spinner } from '../../components/ui'
import { formatPrice } from '../../lib/format'
import { paths } from '../../routes/paths'
import { useAsyncResource } from '../catalog/useAsyncResource'
import { useCart } from '../cart/useCart'
import { useOrdersApi, useWarehousesApi } from './checkoutApiContext'
import {
  buildCheckoutRequest,
  validateCheckout,
  type CheckoutFormErrors,
  type CheckoutFormValues,
} from './checkoutForm'
import {
  fieldErrorsFromValidation,
  GENERIC_VALIDATION_MESSAGE,
  priceChangedMessage,
  stockMessage,
  UNEXPECTED_MESSAGE,
} from './checkoutMessages'
import { CheckoutForm } from './components/CheckoutForm'
import { ConfirmOrderDialog } from './components/ConfirmOrderDialog'
import { PurchaseComplete } from './components/PurchaseComplete'
import styles from './CheckoutFlow.module.css'

type Busy = 'confirm' | 'cancel' | null

interface PageProblem {
  message: string
  /** Offers "Volver al carrito" when the way out is fixing the cart. */
  cartLink: boolean
}

const EMPTY_VALUES: CheckoutFormValues = { name: '', email: '', address: '', method: 'pickup', warehouseId: '' }

/** The order is gone or already settled on the server: there is nothing left to confirm or cancel. */
const isSettled = (error: unknown) =>
  error instanceof ApiRequestError && (error.code === 'ORDER_NOT_PENDING' || error.code === 'ORDER_NOT_FOUND')

const messageOf = (error: unknown) => (error instanceof ApiRequestError ? error.message : UNEXPECTED_MESSAGE)

/** Keeps a delivery method the warehouses can actually serve. */
function usableMethod(values: CheckoutFormValues, warehouses: Warehouse[]): CheckoutFormValues['method'] {
  const canPickup = warehouses.some((warehouse) => warehouse.pickup_enabled)
  const canShip = warehouses.some((warehouse) => warehouse.shipping_enabled)
  if (values.method === 'pickup' && !canPickup && canShip) return 'shipping'
  if (values.method === 'shipping' && !canShip && canPickup) return 'pickup'
  return values.method
}

/**
 * Checkout flow: form -> pending order -> explicit confirmation dialog -> purchase complete.
 * The order is only confirmed by the click on "Confirmar compra" (RF-12). It owns its data
 * access, so any screen can mount it. Personal data only goes into the checkout request.
 */
export function CheckoutFlow() {
  const ordersApi = useOrdersApi()
  const warehousesApi = useWarehousesApi()
  const cart = useCart()
  const warehouses = useAsyncResource('warehouses', (signal) => warehousesApi.listWarehouses(signal))

  const [values, setValues] = useState<CheckoutFormValues>(EMPTY_VALUES)
  const [errors, setErrors] = useState<CheckoutFormErrors>({})
  const [submitting, setSubmitting] = useState(false)
  const [order, setOrder] = useState<Order | null>(null)
  const [busy, setBusy] = useState<Busy>(null)
  const [dialogMessage, setDialogMessage] = useState<string | null>(null)
  const [priceChange, setPriceChange] = useState<string | null>(null)
  const [pageProblem, setPageProblem] = useState<PageProblem | null>(null)
  const [completed, setCompleted] = useState<Order | null>(null)
  // State updates are asynchronous; the ref makes "one request at a time" hold even for fast repeated clicks.
  const inFlight = useRef(false)

  const warehouseList = warehouses.status === 'success' ? warehouses.data : []
  const warehouseNameOf = (target: Order | null) =>
    target?.delivery.method === 'pickup'
      ? warehouseList.find((warehouse) => warehouse.warehouse_id === target.delivery.warehouse_id)?.warehouse_name
      : undefined
  const formValues = { ...values, method: usableMethod(values, warehouseList) }

  const closeDialog = () => {
    setOrder(null)
    setDialogMessage(null)
    setPriceChange(null)
  }

  /** The order is already unusable on the server, so the screen tells the user and offers the cart. */
  const settle = (message: string) => {
    closeDialog()
    setPageProblem({ message, cartLink: true })
    cart.reload()
  }

  // A pending order reserves no stock, so failing to cancel it must not trap the user.
  const cancelQuietly = async (target: Order) => {
    try {
      await ordersApi.cancel(target.order_id)
    } catch {
      /* nothing to do: the pending order stays unconfirmed */
    }
  }

  const handleChange = (next: CheckoutFormValues) => {
    setValues(next)
    setErrors((previous) => {
      const remaining = { ...previous }
      if (next.name !== values.name) delete remaining.name
      if (next.email !== values.email) delete remaining.email
      if (next.address !== values.address) delete remaining.address
      if (next.method !== values.method || next.warehouseId !== values.warehouseId) delete remaining.warehouse
      return remaining
    })
  }

  const handleCheckoutError = (error: unknown) => {
    if (error instanceof ApiRequestError && error.code === 'VALIDATION_ERROR') {
      const fieldErrors = fieldErrorsFromValidation(error.details)
      if (Object.keys(fieldErrors).length > 0) setErrors(fieldErrors)
      else setPageProblem({ message: GENERIC_VALIDATION_MESSAGE, cartLink: false })
      return
    }
    if (error instanceof ApiRequestError && (error.code === 'CART_EMPTY' || error.code === 'INSUFFICIENT_STOCK')) {
      setPageProblem({ message: error.message, cartLink: true })
      cart.reload()
      return
    }
    setPageProblem({ message: messageOf(error), cartLink: false })
  }

  const submit = async () => {
    if (inFlight.current) return
    setPageProblem(null)
    const found = validateCheckout(formValues)
    setErrors(found)
    if (Object.keys(found).length > 0) return

    inFlight.current = true
    setSubmitting(true)
    try {
      setOrder(await ordersApi.checkout(buildCheckoutRequest(formValues)))
    } catch (error) {
      handleCheckoutError(error)
    } finally {
      inFlight.current = false
      setSubmitting(false)
    }
  }

  const handleConfirmError = async (target: Order, error: unknown) => {
    if (error instanceof ApiRequestError && error.code === 'INSUFFICIENT_STOCK') {
      await cancelQuietly(target)
      settle(stockMessage(target, error.details))
    } else if (error instanceof ApiRequestError && error.code === 'PRICE_CHANGED') {
      const message = priceChangedMessage(target, error.details)
      if (message) setPriceChange(message)
      else setDialogMessage(error.message)
    } else if (isSettled(error)) {
      settle(messageOf(error))
    } else {
      setDialogMessage(messageOf(error))
    }
  }

  const confirm = async () => {
    if (inFlight.current || !order) return
    inFlight.current = true
    setBusy('confirm')
    setDialogMessage(null)
    try {
      setCompleted(await ordersApi.confirm(order.order_id))
      closeDialog()
      setPageProblem(null)
      cart.reload()
    } catch (error) {
      await handleConfirmError(order, error)
    } finally {
      inFlight.current = false
      setBusy(null)
    }
  }

  const cancel = async () => {
    if (inFlight.current || !order) return
    inFlight.current = true
    setBusy('cancel')
    setDialogMessage(null)
    try {
      await ordersApi.cancel(order.order_id)
      closeDialog()
    } catch (error) {
      if (isSettled(error)) settle(messageOf(error))
      else setDialogMessage(messageOf(error))
    } finally {
      inFlight.current = false
      setBusy(null)
    }
  }

  const rebuildOrder = async () => {
    if (inFlight.current || !order) return
    inFlight.current = true
    setBusy('cancel')
    try {
      await cancelQuietly(order)
      closeDialog()
      cart.reload()
    } finally {
      inFlight.current = false
      setBusy(null)
    }
  }

  if (completed) {
    return <PurchaseComplete order={completed} warehouseName={warehouseNameOf(completed)} />
  }

  if ((cart.status === 'loading' && !cart.cart) || warehouses.status === 'loading') {
    return (
      <div className={styles.center}>
        <Spinner size="lg" />
      </div>
    )
  }

  if (!cart.cart) {
    return (
      <Card padding="lg" className={styles.status} role="alert">
        <h2 className={styles.statusTitle}>No pudimos cargar tu carrito</h2>
        <p className={styles.muted}>{cart.errorMessage}</p>
        <Button variant="secondary" onClick={cart.reload}>
          Reintentar
        </Button>
      </Card>
    )
  }

  if (warehouses.status === 'error') {
    return (
      <Card padding="lg" className={styles.status} role="alert">
        <h2 className={styles.statusTitle}>No pudimos cargar las opciones de entrega</h2>
        <p className={styles.muted}>{warehouses.message}</p>
        <Button variant="secondary" onClick={warehouses.retry}>
          Reintentar
        </Button>
      </Card>
    )
  }

  const problem = pageProblem && (
    <div role="alert" className={styles.problem}>
      <span>{pageProblem.message}</span>
      {pageProblem.cartLink && <Link to={paths.cart}>Volver al carrito</Link>}
    </div>
  )

  if (cart.cart.items.length === 0) {
    return (
      <div className={styles.flow}>
        {problem}
        <Card padding="lg" className={styles.status} role="status">
          <h2 className={styles.statusTitle}>Tu carrito está vacío</h2>
          <p className={styles.muted}>Sumá productos desde el catálogo para poder comprar.</p>
          <Link to={paths.catalog}>Ver el catálogo</Link>
        </Card>
      </div>
    )
  }

  const itemCount = cart.cart.item_count
  const dialogProblem = priceChange ? (
    <>
      <p>{priceChange}</p>
      <Button variant="secondary" disabled={busy !== null} onClick={() => void rebuildOrder()}>
        Armar la orden de nuevo
      </Button>
    </>
  ) : (
    dialogMessage
  )

  return (
    <section className={styles.flow} aria-labelledby="checkout-title">
      <h1 id="checkout-title" className={styles.title}>
        Finalizar compra
      </h1>
      <p className={styles.muted}>
        {itemCount === 1 ? '1 producto' : `${itemCount} productos`} · Total {formatPrice(cart.cart.total, cart.cart.currency)}
      </p>
      {problem}
      <Card padding="lg" className={styles.card}>
        <CheckoutForm
          values={formValues}
          warehouses={warehouseList}
          errors={errors}
          submitting={submitting}
          onChange={handleChange}
          onSubmit={() => void submit()}
        />
      </Card>
      {order && (
        <ConfirmOrderDialog
          order={order}
          warehouseName={warehouseNameOf(order)}
          pending={busy !== null}
          problem={dialogProblem}
          canConfirm={priceChange === null}
          onConfirm={() => void confirm()}
          onCancel={() => void cancel()}
        />
      )}
    </section>
  )
}
