import { Link } from 'react-router'
import type { Order } from '../../../api/types'
import { Card } from '../../../components/ui'
import { formatDateTime, formatPrice } from '../../../lib/format'
import { paths } from '../../../routes/paths'
import { OrderStatusBadge } from './OrderStatusBadge'
import styles from './OrderList.module.css'

const countItems = (order: Order) => order.items.reduce((sum, item) => sum + item.quantity, 0)

/** The shopper's orders as a list, in the order received. Presentational: it only renders its props. */
export function OrderList({ orders }: { orders: Order[] }) {
  return (
    <ul className={styles.list} aria-label="Mis compras">
      {orders.map((order) => {
        const count = countItems(order)
        return (
          <li key={order.order_id}>
            <Card className={styles.row}>
              <Link to={paths.order(order.order_id)} className={styles.id}>
                {order.order_id}
              </Link>
              <OrderStatusBadge status={order.status} />
              <span className={styles.muted}>{formatDateTime(order.created_at)}</span>
              <span className={styles.muted}>{count === 1 ? '1 producto' : `${count} productos`}</span>
              <strong className={styles.total}>{formatPrice(order.total, order.currency)}</strong>
            </Card>
          </li>
        )
      })}
    </ul>
  )
}
