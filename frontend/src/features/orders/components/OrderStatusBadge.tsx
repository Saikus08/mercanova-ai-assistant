import type { OrderStatus } from '../../../api/types'
import { Badge, type BadgeVariant } from '../../../components/ui'

const STATUS: Record<OrderStatus, { label: string; variant: BadgeVariant }> = {
  confirmed: { label: 'Confirmada', variant: 'success' },
  pending_confirmation: { label: 'Pendiente de confirmación', variant: 'warning' },
  cancelled: { label: 'Cancelada', variant: 'neutral' },
}

/** Order status in words the shopper understands. */
export function OrderStatusBadge({ status }: { status: OrderStatus }) {
  const { label, variant } = STATUS[status]
  return <Badge variant={variant}>{label}</Badge>
}
