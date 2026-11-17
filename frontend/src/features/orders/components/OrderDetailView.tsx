import type { Order } from '../../../api/types'
import { Card } from '../../../components/ui'
import { formatDateTime } from '../../../lib/format'
import { OrderSummary } from '../../checkout/components/OrderSummary'
import { OrderStatusBadge } from './OrderStatusBadge'
import styles from './OrderDetailView.module.css'

export interface OrderDetailViewProps {
  order: Order
  /** Name of the pickup warehouse. The id is shown when it is not known. */
  warehouseName?: string
}

/**
 * One past order: header, dates and, through the checkout `OrderSummary`, the items at the price paid,
 * the total, the delivery and the customer data. Presentational: it only renders its props.
 */
export function OrderDetailView({ order, warehouseName }: OrderDetailViewProps) {
  return (
    <Card padding="lg" className={styles.view}>
      <header className={styles.header}>
        <h1 className={styles.title}>Orden {order.order_id}</h1>
        <OrderStatusBadge status={order.status} />
      </header>
      <dl className={styles.dates}>
        <dt>Creada el</dt>
        <dd>{formatDateTime(order.created_at)}</dd>
        {order.confirmed_at && (
          <>
            <dt>Confirmada el</dt>
            <dd>{formatDateTime(order.confirmed_at)}</dd>
          </>
        )}
      </dl>
      <OrderSummary order={order} warehouseName={warehouseName} />
    </Card>
  )
}
