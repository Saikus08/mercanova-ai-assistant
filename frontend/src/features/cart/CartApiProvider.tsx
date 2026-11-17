import type { ReactNode } from 'react'
import type { CartApi } from '../../api/cart'
import { CartApiContext } from './cartApiContext'

/** Lets tests (or a page) swap the cart API implementation. */
export function CartApiProvider({ api, children }: { api: CartApi; children: ReactNode }) {
  return <CartApiContext.Provider value={api}>{children}</CartApiContext.Provider>
}
