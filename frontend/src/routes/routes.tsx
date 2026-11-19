import { Route, Routes } from 'react-router'
import { CartPage } from '../pages/CartPage'
import { CatalogPage } from '../pages/CatalogPage'
import { ChatPage } from '../pages/ChatPage'
import { CheckoutPage } from '../pages/CheckoutPage'
import { OrderDetailPage } from '../pages/OrderDetailPage'
import { OrdersPage } from '../pages/OrdersPage'
import { ProductDetailPage } from '../pages/ProductDetailPage'
import { UiShowcasePage } from '../pages/UiShowcasePage'
import { paths } from './paths'

export function AppRoutes() {
  return (
    <Routes>
      <Route path={paths.catalog} element={<CatalogPage />} />
      <Route path={paths.productPattern} element={<ProductDetailPage />} />
      <Route path={paths.chat} element={<ChatPage />} />
      <Route path={paths.cart} element={<CartPage />} />
      <Route path={paths.checkout} element={<CheckoutPage />} />
      <Route path={paths.orders} element={<OrdersPage />} />
      <Route path={paths.orderPattern} element={<OrderDetailPage />} />
      <Route path={paths.ui} element={<UiShowcasePage />} />
    </Routes>
  )
}
