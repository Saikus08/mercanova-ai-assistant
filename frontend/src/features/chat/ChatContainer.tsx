import type { ChatProduct } from '../../api/types'
import { AddToCart } from '../cart/AddToCart'
import { ChatView } from './components/ChatView'
import { useChat } from './useChat'

export interface ChatContainerProps {
  /** Opens the checkout screen from a `checkout_draft` block. */
  onCheckout: () => void
}

const renderAddToCart = (product: ChatProduct) => (
  <AddToCart productId={product.product_id} productName={product.name} availableQty={product.available_qty} size="sm" />
)

/** Connects the chat screen with the conversation state and the cart. */
export function ChatContainer({ onCheckout }: ChatContainerProps) {
  const chat = useChat()
  return (
    <ChatView
      turns={chat.turns}
      busy={chat.busy}
      onSend={chat.send}
      onCheckout={onCheckout}
      renderProductActions={renderAddToCart}
    />
  )
}
