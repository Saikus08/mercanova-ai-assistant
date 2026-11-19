import type { ReactNode } from 'react'
import type { ChatBlock, ChatProduct } from '../../../api/types'
import { CartUpdatedNotice } from './CartUpdatedNotice'
import { CheckoutDraftSummary } from './CheckoutDraftSummary'
import { ClarificationOptions } from './ClarificationOptions'
import { ComparisonTable } from './ComparisonTable'
import { NotFoundNotice } from './NotFoundNotice'
import { ProductRecommendations } from './ProductRecommendations'

export interface BlockActions {
  renderProductActions?: (product: ChatProduct) => ReactNode
  onSelectOption: (option: string) => void
  onCheckout: () => void
}

export interface ChatBlockViewProps extends BlockActions {
  block: ChatBlock
  /** Quick replies only work on the latest answer, once it is complete. */
  optionsDisabled?: boolean
}

/** One component per block type of the contract (docs/api-contract.md, "Bloques"). */
export function ChatBlockView({ block, renderProductActions, onSelectOption, onCheckout, optionsDisabled }: ChatBlockViewProps) {
  switch (block.type) {
    case 'product_recommendations':
      return <ProductRecommendations block={block} renderActions={renderProductActions} />
    case 'comparison':
      return <ComparisonTable block={block} />
    case 'clarification':
      return <ClarificationOptions block={block} onSelect={onSelectOption} disabled={optionsDisabled} />
    case 'cart_updated':
      return <CartUpdatedNotice block={block} />
    case 'checkout_draft':
      return <CheckoutDraftSummary block={block} onCheckout={onCheckout} />
    case 'not_found':
      return <NotFoundNotice block={block} />
    default:
      // A block type this version of the interface does not know is skipped.
      return null
  }
}
