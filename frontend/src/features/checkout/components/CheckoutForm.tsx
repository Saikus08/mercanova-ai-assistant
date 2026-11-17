import { useId, type FormEvent } from 'react'
import type { DeliveryMethod, Warehouse } from '../../../api/types'
import { Button, Input } from '../../../components/ui'
import type { CheckoutFormErrors, CheckoutFormValues } from '../checkoutForm'
import styles from './CheckoutForm.module.css'

export interface CheckoutFormProps {
  values: CheckoutFormValues
  warehouses: Warehouse[]
  /** Spanish message per field. */
  errors: CheckoutFormErrors
  submitting: boolean
  onChange: (values: CheckoutFormValues) => void
  onSubmit: () => void
}

/** Customer data and delivery choice. It never asks for card data: the purchase is fictitious (RF-13). */
export function CheckoutForm({ values, warehouses, errors, submitting, onChange, onSubmit }: CheckoutFormProps) {
  const selectId = useId()
  const pickupWarehouses = warehouses.filter((warehouse) => warehouse.pickup_enabled)
  const canPickup = pickupWarehouses.length > 0
  const canShip = warehouses.some((warehouse) => warehouse.shipping_enabled)
  const warehouseMessageId = `${selectId}-message`

  const set = <K extends keyof CheckoutFormValues>(key: K, value: CheckoutFormValues[K]) =>
    onChange({ ...values, [key]: value })

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault()
    onSubmit()
  }

  return (
    <form className={styles.form} onSubmit={handleSubmit} noValidate>
      <Input
        label="Nombre"
        name="name"
        autoComplete="name"
        required
        value={values.name}
        error={errors.name}
        onChange={(event) => set('name', event.target.value)}
      />
      <Input
        label="Email"
        name="email"
        type="email"
        autoComplete="email"
        required
        value={values.email}
        error={errors.email}
        onChange={(event) => set('email', event.target.value)}
      />
      <Input
        label="Dirección"
        name="address"
        autoComplete="street-address"
        required
        value={values.address}
        error={errors.address}
        onChange={(event) => set('address', event.target.value)}
      />

      <fieldset className={styles.delivery}>
        <legend className={styles.legend}>Entrega</legend>
        {!canPickup && !canShip && <p className={styles.muted}>Por ahora no hay opciones de entrega disponibles.</p>}
        {canPickup && (
          <label className={styles.option}>
            <input
              type="radio"
              name="delivery-method"
              checked={values.method === 'pickup'}
              onChange={() => set('method', 'pickup' satisfies DeliveryMethod)}
            />
            Retiro en depósito
          </label>
        )}
        {canPickup && values.method === 'pickup' && (
          <div className={styles.field}>
            <label htmlFor={selectId} className={styles.label}>
              Depósito de retiro
            </label>
            <select
              id={selectId}
              className={styles.select}
              value={values.warehouseId}
              aria-invalid={errors.warehouse ? true : undefined}
              aria-describedby={errors.warehouse ? warehouseMessageId : undefined}
              onChange={(event) => set('warehouseId', event.target.value)}
            >
              <option value="">Elegí un depósito</option>
              {pickupWarehouses.map((warehouse) => (
                <option key={warehouse.warehouse_id} value={warehouse.warehouse_id}>
                  {warehouse.warehouse_name} ({warehouse.city})
                </option>
              ))}
            </select>
            {errors.warehouse && (
              <p id={warehouseMessageId} className={styles.error}>
                {errors.warehouse}
              </p>
            )}
          </div>
        )}
        {canShip && (
          <label className={styles.option}>
            <input
              type="radio"
              name="delivery-method"
              checked={values.method === 'shipping'}
              onChange={() => set('method', 'shipping' satisfies DeliveryMethod)}
            />
            Envío a domicilio
          </label>
        )}
      </fieldset>

      <Button type="submit" disabled={submitting || (!canPickup && !canShip)}>
        Revisar compra
      </Button>
    </form>
  )
}
