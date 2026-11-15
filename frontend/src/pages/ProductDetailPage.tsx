import { useParams } from 'react-router'
import { ProductDetailContainer } from '../features/catalog/ProductDetailContainer'

export function ProductDetailPage() {
  const { productId = '' } = useParams()
  // `key` resets the loaded state when navigating between related products.
  return <ProductDetailContainer key={productId} productId={productId} />
}
