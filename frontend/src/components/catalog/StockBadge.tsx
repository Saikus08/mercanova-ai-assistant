import { Badge } from '../ui'

/** Few units left: the badge turns into a warning. */
export const LOW_STOCK_THRESHOLD = 3

export function StockBadge({ availableQty }: { availableQty: number }) {
  if (availableQty <= 0) return <Badge variant="danger">Sin stock</Badge>
  if (availableQty <= LOW_STOCK_THRESHOLD) {
    return (
      <Badge variant="warning">
        {availableQty === 1 ? 'Última unidad' : `Últimas ${availableQty} unidades`}
      </Badge>
    )
  }
  return <Badge variant="success">En stock</Badge>
}
