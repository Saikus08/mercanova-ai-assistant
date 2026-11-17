import { useNavigate } from 'react-router'
import { CartContainer } from '../features/cart/CartContainer'
import { paths } from '../routes/paths'

export function CartPage() {
  const navigate = useNavigate()
  return <CartContainer onCheckout={() => navigate(paths.checkout)} />
}
