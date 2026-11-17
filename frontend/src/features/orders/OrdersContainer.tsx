import { Link } from 'react-router'
import { Spinner } from '../../components/ui'
import { paths } from '../../routes/paths'
import { StatusMessage } from '../catalog/components/StatusMessage'
import { useAsyncResource } from '../catalog/useAsyncResource'
import { useOrdersApi } from '../checkout/checkoutApiContext'
import { OrderList } from './components/OrderList'
import styles from './OrdersContainer.module.css'

/** Order history (RF-16). Always loaded from the API: prices are the ones paid at purchase time. */
export function OrdersContainer() {
  const api = useOrdersApi()
  const orders = useAsyncResource('orders', (signal) => api.list(signal))

  return (
    <div className={styles.page}>
      <h1 className={styles.title}>Mis compras</h1>

      {orders.status === 'loading' && (
        <div className={styles.loading}>
          <Spinner size="lg" label="Cargando tus compras…" />
        </div>
      )}

      {orders.status === 'error' && (
        <StatusMessage
          tone="error"
          title="No pudimos cargar tus compras"
          message={orders.message}
          actionLabel="Reintentar"
          onAction={orders.retry}
        />
      )}

      {orders.status === 'success' &&
        (orders.data.length === 0 ? (
          <>
            <StatusMessage title="Todavía no hiciste compras" message="Cuando compres, vas a ver tus órdenes acá." />
            <Link to={paths.catalog} className={styles.link}>
              Ir al catálogo
            </Link>
          </>
        ) : (
          <OrderList orders={orders.data} />
        ))}
    </div>
  )
}
