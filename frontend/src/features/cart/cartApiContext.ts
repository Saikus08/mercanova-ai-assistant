import { createContext, useContext } from 'react'
import { httpCartApi, type CartApi } from '../../api/cart'

export const CartApiContext = createContext<CartApi>(httpCartApi)

export function useCartApi(): CartApi {
  return useContext(CartApiContext)
}
