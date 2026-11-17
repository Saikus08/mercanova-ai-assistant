import { Link } from 'react-router'
import type { Order } from '../../../api/types'
import { Card } from '../../../components/ui'
import { paths } from '../../../routes/paths'
import { OrderSummary } from './OrderSummary'
import styles from './PurchaseComplete.module.css'

export interface PurchaseCompleteProps {
  order: Order
  warehouseName?: string
  /** Where "Seguir comprando" goes. Defaults to the catalog. */
  catalogPath?: string
}

export function PurchaseComplete({ order, warehouseName, catalogPath = paths.catalog }: PurchaseCompleteProps) {
  return (
    <Card padding="lg" className={styles.complete} role="status">
      <h2 className={styles.title}>¡Compra confirmada!</h2>
      <p>
        Número de orden: <strong>{order.order_id}</strong>
      </p>
      <OrderSummary order={order} warehouseName={warehouseName} />
      <Link to={catalogPath}>Seguir comprando</Link>
    </Card>
  )
}
