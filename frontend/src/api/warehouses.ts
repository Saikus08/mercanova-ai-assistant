import { apiGet } from './http'
import type { Warehouse } from './types'

/** Reference data endpoint (docs/api-contract.md, "Estado y datos de referencia"). */
export interface WarehousesApi {
  listWarehouses(signal?: AbortSignal): Promise<Warehouse[]>
}

export const httpWarehousesApi: WarehousesApi = {
  listWarehouses: (signal) => apiGet<Warehouse[]>('/warehouses', signal),
}
