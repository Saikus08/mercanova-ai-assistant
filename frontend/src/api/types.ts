/**
 * Types that mirror the API contract (docs/api-contract.md).
 * Field names stay in snake_case to match the JSON exactly. If the contract changes,
 * update this file in the same pull request.
 */

// ---------- Common ----------

export type Currency = 'USD'

/** ISO 8601 date-time in UTC, e.g. "2026-11-12T22:00:00Z". */
export type IsoDateTime = string

export interface Paginated<T> {
  items: T[]
  page: number
  page_size: number
  total: number
}

// ---------- Errors ----------

export type ApiErrorCode =
  | 'VALIDATION_ERROR'
  | 'MISSING_SESSION'
  | 'PRODUCT_NOT_FOUND'
  | 'ORDER_NOT_FOUND'
  | 'INSUFFICIENT_STOCK'
  | 'PRODUCT_INACTIVE'
  | 'CART_EMPTY'
  | 'PRICE_CHANGED'
  | 'ORDER_NOT_PENDING'
  | 'AUDIO_UNREADABLE'
  | 'LLM_UNAVAILABLE'
  | 'STT_UNAVAILABLE'
  | 'INTERNAL_ERROR'
  | 'NOT_FOUND'
  | 'METHOD_NOT_ALLOWED'
  | 'HTTP_ERROR'
  | 'CONVERSATION_NOT_FOUND'

export interface ApiErrorBody {
  code: ApiErrorCode
  /** Spanish message that can be shown to the user as is. */
  message: string
  details?: Record<string, unknown>
}

/** Every error response has this shape. */
export interface ApiError {
  error: ApiErrorBody
}

// ---------- Health ----------

export type ServiceStatus = 'ok' | 'down'

export interface HealthStatus {
  status: ServiceStatus
  db: ServiceStatus
  llm: ServiceStatus
  stt: ServiceStatus
}

// ---------- Categories ----------

/** One entry of GET /api/categories. Names match `category` / `subcategory` of products. */
export interface CategoryGroup {
  category: string
  subcategories: string[]
}

export type CategoryList = CategoryGroup[]

// ---------- Products ----------

export interface Price {
  current: number
  list: number
  discount_percent: number
  currency: Currency
}

/** Summary used in listings and assistant product cards. */
export interface ProductSummary {
  product_id: string
  sku: string
  name: string
  brand: string
  category: string
  subcategory: string
  short_description: string
  image_url: string
  rating: number
  review_count: number
  price: Price
  /** Sum of available units across all warehouses. */
  available_qty: number
  in_stock: boolean
}

export interface Dimensions {
  width: number
  height: number
  depth: number
}

export interface Specification {
  group: string
  name: string
  value: string
  unit: string | null
}

export interface WarehouseAvailability {
  warehouse_id: string
  warehouse_name: string
  city: string
  available_qty: number
  pickup_enabled: boolean
}

export interface RelatedProduct {
  product_id: string
  name: string
  /** e.g. "alternative_to". */
  relation_type: string
  strength: number
}

export interface ProductDetail extends ProductSummary {
  description: string
  recommended_for: string[]
  not_recommended_for: string[]
  key_features: string[]
  tags: string[]
  color: string
  dimensions_cm: Dimensions
  weight_kg: number
  warranty_months: number
  return_days: number
  specifications: Specification[]
  availability: WarehouseAvailability[]
  related: RelatedProduct[]
}

export type ProductSort = 'price_asc' | 'price_desc' | 'rating'

/** Query parameters for GET /api/products. */
export interface ProductListParams {
  q?: string
  category?: string
  subcategory?: string
  brand?: string
  min_price?: number
  max_price?: number
  in_stock?: boolean
  sort?: ProductSort
  page?: number
  /** 20 by default, 100 max. */
  page_size?: number
}

export type ProductList = Paginated<ProductSummary>

export interface ComparisonAttribute {
  group: string
  name: string
  unit: string | null
  /** Value per product, keyed by product_id. */
  values: Record<string, string>
}

/** Response of GET /api/products/compare. */
export interface ProductComparison {
  products: ProductSummary[]
  attributes: ComparisonAttribute[]
}

// ---------- Cart ----------

export interface CartItem {
  product_id: string
  name: string
  /** The backend can return null when the product has no image. */
  image_url: string | null
  unit_price: number
  quantity: number
  line_total: number
  available_qty: number
}

export interface Cart {
  items: CartItem[]
  item_count: number
  total: number
  currency: Currency
}

export interface AddCartItemRequest {
  product_id: string
  quantity: number
}

export interface UpdateCartItemRequest {
  /** Minimum 1. */
  quantity: number
}

// ---------- Orders ----------

export type OrderStatus = 'pending_confirmation' | 'confirmed' | 'cancelled'

export type DeliveryMethod = 'pickup' | 'shipping'

export interface Customer {
  name: string
  email: string
  address: string
}

export type Delivery =
  | { method: 'pickup'; warehouse_id: string }
  | { method: 'shipping'; warehouse_id?: null }

export interface OrderItem {
  product_id: string
  name: string
  /** Price at the moment of purchase. */
  unit_price: number
  quantity: number
  line_total: number
}

export interface Order {
  order_id: string
  status: OrderStatus
  created_at: IsoDateTime
  confirmed_at: IsoDateTime | null
  customer: Customer
  delivery: Delivery
  items: OrderItem[]
  total: number
  currency: Currency
}

/** Body of POST /api/checkout (step 1: creates a pending order). */
export interface CheckoutRequest {
  customer: Customer
  delivery: Delivery
}

// ---------- Chat ----------

export type InputMode = 'text' | 'voice'

export interface ChatRequest {
  message: string
  /** null on the first message of a conversation. */
  conversation_id: string | null
  input_mode: InputMode
}

export interface ToolUsage {
  name: string
  args: Record<string, unknown>
}

export interface ProductRecommendation {
  product: ProductSummary
  reason: string
}

export interface ProductRecommendationsBlock {
  type: 'product_recommendations'
  items: ProductRecommendation[]
}

export interface ComparisonBlock extends ProductComparison {
  type: 'comparison'
}

export interface ClarificationBlock {
  type: 'clarification'
  question: string
  options: string[]
}

export interface CartUpdatedBlock {
  type: 'cart_updated'
  cart: Cart
}

/** Opens the purchase confirmation modal. Only the user confirms the order. */
export interface CheckoutDraftBlock {
  type: 'checkout_draft'
  order: Order
}

export interface NotFoundBlock {
  type: 'not_found'
  query: string
}

/** Rich content the assistant can return. Discriminated by `type`. */
export type ChatBlock =
  | ProductRecommendationsBlock
  | ComparisonBlock
  | ClarificationBlock
  | CartUpdatedBlock
  | CheckoutDraftBlock
  | NotFoundBlock

export type ChatBlockType = ChatBlock['type']

/** Response of POST /api/chat (non-streaming fallback). */
export interface ChatResponse {
  conversation_id: string
  reply: string
  blocks: ChatBlock[]
  tools_used: ToolUsage[]
}

export type ChatRole = 'user' | 'assistant'

export interface ChatMessage {
  role: ChatRole
  content: string
  blocks: ChatBlock[]
  created_at: IsoDateTime
}

/** Response of GET /api/chat/{conversation_id}. */
export interface ChatHistory {
  conversation_id: string
  messages: ChatMessage[]
}

// ---------- Chat streaming (SSE over POST /api/chat/stream) ----------

export interface MetaEventData {
  conversation_id: string
}

export type ToolCallEventData = ToolUsage

export interface TokenEventData {
  text: string
}

export interface DoneEventData {
  reply: string
  tools_used: ToolUsage[]
}

export type ChatStreamEvent =
  | { event: 'meta'; data: MetaEventData }
  | { event: 'tool_call'; data: ToolCallEventData }
  | { event: 'token'; data: TokenEventData }
  | { event: 'block'; data: ChatBlock }
  | { event: 'done'; data: DoneEventData }
  | { event: 'error'; data: ApiError }

export type ChatStreamEventName = ChatStreamEvent['event']

// ---------- Voice ----------

/** Response of POST /api/transcribe. */
export interface TranscriptionResponse {
  text: string
  language: string
  duration_s: number
}
