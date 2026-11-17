import { createContext, useContext } from 'react'
import { httpOrdersApi, type OrdersApi } from '../../api/orders'
import { httpWarehousesApi, type WarehousesApi } from '../../api/warehouses'

export const OrdersApiContext = createContext<OrdersApi>(httpOrdersApi)
export const WarehousesApiContext = createContext<WarehousesApi>(httpWarehousesApi)

export function useOrdersApi(): OrdersApi {
  return useContext(OrdersApiContext)
}

export function useWarehousesApi(): WarehousesApi {
  return useContext(WarehousesApiContext)
}
