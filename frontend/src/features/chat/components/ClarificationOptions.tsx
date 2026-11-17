import type { ClarificationBlock } from '../../../api/types'
import { Button } from '../../../components/ui'
import styles from './ClarificationOptions.module.css'

export interface ClarificationOptionsProps {
  block: ClarificationBlock
  /** Sends the option as the user's next message. */
  onSelect: (option: string) => void
  /** Options of older turns, or while an answer is being written. */
  disabled?: boolean
}

/** Block `clarification`: the question with quick reply buttons (RF-05). */
export function ClarificationOptions({ block, onSelect, disabled = false }: ClarificationOptionsProps) {
  return (
    <div className={styles.box}>
      <p className={styles.question}>{block.question}</p>
      <div role="group" aria-label="Respuestas rápidas" className={styles.options}>
        {block.options.map((option) => (
          <Button key={option} variant="secondary" size="sm" disabled={disabled} onClick={() => onSelect(option)}>
            {option}
          </Button>
        ))}
      </div>
    </div>
  )
}
