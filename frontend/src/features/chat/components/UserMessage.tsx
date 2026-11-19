import { cx } from '../../../components/ui/cx'
import styles from './ChatMessage.module.css'

/** A message written by the user. */
export function UserMessage({ text }: { text: string }) {
  return (
    <article className={cx(styles.row, styles.userRow)} aria-label="Tu mensaje">
      <p className={cx(styles.bubble, styles.user)}>{text}</p>
    </article>
  )
}
