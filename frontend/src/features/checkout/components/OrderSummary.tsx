import type { Order } from '../../../api/types'
import { formatPrice } from '../../../lib/format'
import styles from './OrderSummary.module.css'

export interface OrderSummaryProps {
  order: Order
  /** Name of the pickup warehouse. The id is shown when it is not known. */
  warehouseName?: string
}

/** Items, total, delivery and customer data of an order. Presentational: it only renders its props. */
export function OrderSummary({ order, warehouseName }: OrderSummaryProps) {
  const delivery =
    order.delivery.method === 'pickup'
      ? `Retiro en depósito: ${warehouseName ?? order.delivery.warehouse_id}`
      : 'Envío a domicilio'

  return (
    <section className={styles.summary} aria-label="Resumen de la orden">
      <ul className={styles.items} aria-label="Productos de la orden">
        {order.items.map((item) => (
          <li key={item.product_id} className={styles.item}>
            <span className={styles.name}>{item.name}</span>
            <span className={styles.muted}>
              {item.quantity} × {formatPrice(item.unit_price, order.currency)}
            </span>
            <strong className={styles.lineTotal}>{formatPrice(item.line_total, order.currency)}</strong>
          </li>
        ))}
      </ul>
      <p className={styles.total}>
        <span>Total</span>
        <strong>{formatPrice(order.total, order.currency)}</strong>
      </p>
      <dl className={styles.details}>
        <dt>Entrega</dt>
        <dd>{delivery}</dd>
        <dt>Nombre</dt>
        <dd>{order.customer.name}</dd>
        <dt>Email</dt>
        <dd>{order.customer.email}</dd>
        <dt>Dirección</dt>
        <dd>{order.customer.address}</dd>
      </dl>
    </section>
  )
}
