import { useParams } from 'react-router'
import { OrderDetailContainer } from '../features/orders/OrderDetailContainer'

export function OrderDetailPage() {
  const { orderId = '' } = useParams()
  // `key` resets the loaded state when navigating between orders.
  return <OrderDetailContainer key={orderId} orderId={orderId} />
}
