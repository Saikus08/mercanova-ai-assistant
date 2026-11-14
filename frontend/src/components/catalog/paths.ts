export function productPath(productId: string): string {
  return `/productos/${encodeURIComponent(productId)}`
}
