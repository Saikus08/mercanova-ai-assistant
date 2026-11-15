import type { CategoryList, ProductDetail, WarehouseAvailability } from '../types'

/**
 * Simulated catalog used while the backend endpoints are not ready (VITE_USE_MOCKS=true) and in
 * tests. Values are made up but follow the shapes of docs/api-contract.md.
 */

export const mockCategories: CategoryList = [
  { category: 'Monitors', subcategories: ['Gaming', 'Office'] },
  { category: 'Headphones', subcategories: ['Wireless', 'Wired'] },
  { category: 'Laptops', subcategories: ['Ultrabook', 'Gaming'] },
]

const warehouses = [
  { warehouse_id: 'WH-MVD-CEN', warehouse_name: 'MercaNova Centro', city: 'Montevideo', pickup_enabled: true },
  { warehouse_id: 'WH-MVD-POC', warehouse_name: 'MercaNova Pocitos', city: 'Montevideo', pickup_enabled: true },
  { warehouse_id: 'WH-CAN-LPZ', warehouse_name: 'MercaNova Las Piedras', city: 'Canelones', pickup_enabled: false },
] as const

function availability(quantities: [number, number, number]): WarehouseAvailability[] {
  return warehouses.map((warehouse, index) => ({ ...warehouse, available_qty: quantities[index] }))
}

interface MockProductInput {
  product_id: string
  sku: string
  name: string
  brand: string
  category: string
  subcategory: string
  short_description: string
  current: number
  list: number
  rating: number
  review_count: number
  stock: [number, number, number]
  key_features: string[]
  recommended_for: string[]
  not_recommended_for: string[]
  specifications: ProductDetail['specifications']
  related?: ProductDetail['related']
}

function product(input: MockProductInput): ProductDetail {
  const { current, list, stock, ...rest } = input
  const available = availability(stock)
  const availableQty = available.reduce((total, warehouse) => total + warehouse.available_qty, 0)
  return {
    ...rest,
    image_url: `https://placehold.co/800x600/png?text=${input.sku}`,
    price: {
      current,
      list,
      discount_percent: Math.round((1 - current / list) * 100),
      currency: 'USD',
    },
    available_qty: availableQty,
    in_stock: availableQty > 0,
    description: `${input.short_description} Simulated product used for frontend development.`,
    tags: [input.category.toLowerCase(), input.subcategory.toLowerCase()],
    color: 'Black',
    dimensions_cm: { width: 50.4, height: 32.4, depth: 23.9 },
    weight_kg: 2.5,
    warranty_months: 12,
    return_days: 30,
    availability: available,
    related: input.related ?? [],
  }
}

export const mockProducts: ProductDetail[] = [
  product({
    product_id: 'MN-MON-0001',
    sku: 'MON-10000',
    name: 'Flux Vision 24 QHD IPS',
    brand: 'Flux',
    category: 'Monitors',
    subcategory: 'Gaming',
    short_description: '24-inch QHD IPS monitor with 240 Hz refresh rate.',
    current: 468.62,
    list: 493.28,
    rating: 4.3,
    review_count: 1088,
    stock: [7, 5, 2],
    key_features: ['24-inch', 'QHD', 'IPS', '240 Hz'],
    recommended_for: ['competitive gaming', 'programming'],
    not_recommended_for: ['color-critical photo editing'],
    specifications: [
      { group: 'Display', name: 'Screen Size', value: '24', unit: 'in' },
      { group: 'Display', name: 'Refresh Rate', value: '240', unit: 'Hz' },
      { group: 'Connectivity', name: 'Ports', value: 'HDMI 2.1, DisplayPort 1.4', unit: null },
    ],
    related: [{ product_id: 'MN-MON-0002', name: 'Flux Office 27 FHD', relation_type: 'alternative_to', strength: 0.82 }],
  }),
  product({
    product_id: 'MN-MON-0002',
    sku: 'MON-10001',
    name: 'Flux Office 27 FHD',
    brand: 'Flux',
    category: 'Monitors',
    subcategory: 'Office',
    short_description: '27-inch Full HD monitor with eye-care mode.',
    current: 189.9,
    list: 189.9,
    rating: 4.1,
    review_count: 342,
    stock: [10, 4, 6],
    key_features: ['27-inch', 'Full HD', 'Flicker free'],
    recommended_for: ['office work', 'studying'],
    not_recommended_for: ['competitive gaming'],
    specifications: [
      { group: 'Display', name: 'Screen Size', value: '27', unit: 'in' },
      { group: 'Display', name: 'Refresh Rate', value: '75', unit: 'Hz' },
    ],
  }),
  product({
    product_id: 'MN-MON-0003',
    sku: 'MON-10002',
    name: 'Orion Pro 32 4K',
    brand: 'Orion',
    category: 'Monitors',
    subcategory: 'Office',
    short_description: '32-inch 4K monitor with USB-C power delivery.',
    current: 529,
    list: 599,
    rating: 4.6,
    review_count: 215,
    stock: [0, 0, 0],
    key_features: ['32-inch', '4K', 'USB-C 90 W'],
    recommended_for: ['design', 'programming'],
    not_recommended_for: ['small desks'],
    specifications: [{ group: 'Display', name: 'Screen Size', value: '32', unit: 'in' }],
  }),
  product({
    product_id: 'MN-HEA-0001',
    sku: 'HEA-20000',
    name: 'Echo Calm ANC',
    brand: 'Echo',
    category: 'Headphones',
    subcategory: 'Wireless',
    short_description: 'Over-ear wireless headphones with active noise cancellation.',
    current: 179,
    list: 199,
    rating: 4.5,
    review_count: 2310,
    stock: [12, 8, 3],
    key_features: ['ANC', '30 h battery', 'Dual microphone'],
    recommended_for: ['video calls', 'travel'],
    not_recommended_for: ['sports'],
    specifications: [
      { group: 'Audio', name: 'Battery Life', value: '30', unit: 'h' },
      { group: 'Connectivity', name: 'Bluetooth', value: '5.3', unit: null },
    ],
  }),
  product({
    product_id: 'MN-HEA-0002',
    sku: 'HEA-20001',
    name: 'Echo Studio Wired',
    brand: 'Echo',
    category: 'Headphones',
    subcategory: 'Wired',
    short_description: 'Closed-back studio headphones with detachable cable.',
    current: 89.5,
    list: 89.5,
    rating: 4.2,
    review_count: 560,
    stock: [1, 0, 0],
    key_features: ['Closed-back', '3.5 mm', 'Detachable cable'],
    recommended_for: ['music production'],
    not_recommended_for: ['video calls'],
    specifications: [{ group: 'Audio', name: 'Impedance', value: '32', unit: 'ohm' }],
  }),
  product({
    product_id: 'MN-LAP-0001',
    sku: 'LAP-30000',
    name: 'Nimbus Air 14',
    brand: 'Nimbus',
    category: 'Laptops',
    subcategory: 'Ultrabook',
    short_description: '14-inch ultrabook, 16 GB RAM, 512 GB SSD, 1.2 kg.',
    current: 1099,
    list: 1249,
    rating: 4.4,
    review_count: 780,
    stock: [3, 2, 0],
    key_features: ['16 GB RAM', '512 GB SSD', '1.2 kg'],
    recommended_for: ['office work', 'travel'],
    not_recommended_for: ['3D gaming'],
    specifications: [
      { group: 'Performance', name: 'RAM', value: '16', unit: 'GB' },
      { group: 'Storage', name: 'SSD', value: '512', unit: 'GB' },
    ],
  }),
  product({
    product_id: 'MN-LAP-0002',
    sku: 'LAP-30001',
    name: 'Titan G15 RTX',
    brand: 'Titan',
    category: 'Laptops',
    subcategory: 'Gaming',
    short_description: '15.6-inch gaming laptop with dedicated graphics and 165 Hz screen.',
    current: 1599,
    list: 1599,
    rating: 4.0,
    review_count: 410,
    stock: [2, 1, 1],
    key_features: ['165 Hz', 'Dedicated GPU', '32 GB RAM'],
    recommended_for: ['gaming', 'video editing'],
    not_recommended_for: ['long battery life'],
    specifications: [{ group: 'Performance', name: 'RAM', value: '32', unit: 'GB' }],
  }),
]
