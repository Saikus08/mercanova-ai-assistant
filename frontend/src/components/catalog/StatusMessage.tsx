import { Button, Card } from '../ui'
import styles from './StatusMessage.module.css'

export interface StatusMessageProps {
  title: string
  message: string
  /** `error` is announced to screen readers immediately. */
  tone?: 'neutral' | 'error'
  actionLabel?: string
  onAction?: () => void
}

/** Empty and error states of async views. */
export function StatusMessage({ title, message, tone = 'neutral', actionLabel, onAction }: StatusMessageProps) {
  return (
    <Card padding="lg" className={styles.box} role={tone === 'error' ? 'alert' : 'status'}>
      <h2 className={styles.title}>{title}</h2>
      <p className={styles.message}>{message}</p>
      {actionLabel && onAction && (
        <Button variant="secondary" onClick={onAction}>
          {actionLabel}
        </Button>
      )}
    </Card>
  )
}
