import type { ChatProduct } from '../../api/types'
import { AddToCart } from '../cart/AddToCart'
import { ChatView } from './components/ChatView'
import { useChat } from './useChat'
import { MAX_RECORDING_SECONDS, useVoiceRecorder } from './useVoiceRecorder'

export interface ChatContainerProps {
  /** Opens the checkout screen from a `checkout_draft` block. */
  onCheckout: () => void
}

const renderAddToCart = (product: ChatProduct) => (
  <AddToCart productId={product.product_id} productName={product.name} availableQty={product.available_qty} size="sm" />
)

/** Connects the chat screen with the conversation state, the cart and the voice input. */
export function ChatContainer({ onCheckout }: ChatContainerProps) {
  const chat = useChat()
  // The transcript is sent as is, through the same path as a typed message.
  const recorder = useVoiceRecorder((text) => chat.send(text, 'voice'))
  return (
    <ChatView
      turns={chat.turns}
      busy={chat.busy}
      onSend={chat.send}
      onCheckout={onCheckout}
      renderProductActions={renderAddToCart}
      voice={{
        status: recorder.status,
        elapsedSeconds: recorder.elapsedSeconds,
        maxSeconds: MAX_RECORDING_SECONDS,
        error: recorder.error,
        onStart: recorder.start,
        onStop: recorder.stop,
      }}
    />
  )
}
