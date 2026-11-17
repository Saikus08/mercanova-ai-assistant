import { Link } from 'react-router'
import { Spinner } from '../../components/ui'
import { paths } from '../../routes/paths'
import { StatusMessage } from '../catalog/components/StatusMessage'
import { useAsyncResource } from '../catalog/useAsyncResource'
import { useOrdersApi } from '../checkout/checkoutApiContext'
import { OrderDetailView } from './components/OrderDetailView'
import styles from './OrdersContainer.module.css'

/** One past order (RF-16). The API only returns orders of the current session. */
export function OrderDetailContainer({ orderId }: { orderId: string }) {
  const api = useOrdersApi()
  const order = useAsyncResource(orderId, (signal) => api.get(orderId, signal))

  return (
    <div className={styles.page}>
      <Link to={paths.orders} className={styles.link}>
        ← Volver a mis compras
      </Link>

      {order.status === 'loading' && (
        <div className={styles.loading}>
          <Spinner size="lg" label="Cargando la orden…" />
        </div>
      )}

      {order.status === 'error' &&
        (order.code === 'ORDER_NOT_FOUND' ? (
          <StatusMessage title="La orden no existe." message="Revisá el enlace o buscala en tus compras." />
        ) : (
          <StatusMessage
            tone="error"
            title="No pudimos cargar la orden"
            message={order.message}
            actionLabel="Reintentar"
            onAction={order.retry}
          />
        ))}

      {order.status === 'success' && <OrderDetailView order={order.data} />}
    </div>
  )
}
