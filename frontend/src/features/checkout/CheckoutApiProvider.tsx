import type { ReactNode } from 'react'
import { httpOrdersApi, type OrdersApi } from '../../api/orders'
import { httpWarehousesApi, type WarehousesApi } from '../../api/warehouses'
import { OrdersApiContext, WarehousesApiContext } from './checkoutApiContext'

/** Lets tests (or a page) swap the orders and warehouses API implementations. */
export function CheckoutApiProvider({
  ordersApi = httpOrdersApi,
  warehousesApi = httpWarehousesApi,
  children,
}: {
  ordersApi?: OrdersApi
  warehousesApi?: WarehousesApi
  children: ReactNode
}) {
  return (
    <OrdersApiContext.Provider value={ordersApi}>
      <WarehousesApiContext.Provider value={warehousesApi}>{children}</WarehousesApiContext.Provider>
    </OrdersApiContext.Provider>
  )
}
