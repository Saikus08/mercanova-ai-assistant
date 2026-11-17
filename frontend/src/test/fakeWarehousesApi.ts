import type { WarehousesApi } from '../api/warehouses'
import type { Warehouse } from '../api/types'

export const fakeWarehouses: Warehouse[] = [
  {
    warehouse_id: 'WH-MVD-CEN',
    warehouse_name: 'Depósito Centro',
    city: 'Montevideo',
    department: 'Montevideo',
    country: 'UY',
    pickup_enabled: true,
    shipping_enabled: true,
  },
  {
    warehouse_id: 'WH-CAN-001',
    warehouse_name: 'Depósito Canelones',
    city: 'Las Piedras',
    department: 'Canelones',
    country: 'UY',
    pickup_enabled: true,
    shipping_enabled: false,
  },
  {
    warehouse_id: 'WH-LOG-001',
    warehouse_name: 'Centro Logístico',
    city: 'Montevideo',
    department: 'Montevideo',
    country: 'UY',
    pickup_enabled: false,
    shipping_enabled: true,
  },
]

export function createFakeWarehousesApi(warehouses: Warehouse[] = fakeWarehouses): WarehousesApi {
  return { listWarehouses: async () => warehouses }
}
