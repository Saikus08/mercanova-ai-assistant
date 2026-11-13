import { cx } from './cx'
import styles from './Spinner.module.css'

export type SpinnerSize = 'sm' | 'md' | 'lg'

export interface SpinnerProps {
  size?: SpinnerSize
  /** Text announced to screen readers. */
  label?: string
  className?: string
}

export function Spinner({ size = 'md', label = 'Cargando…', className }: SpinnerProps) {
  return (
    <span role="status" className={cx(styles.wrapper, className)}>
      <span aria-hidden="true" className={cx(styles.spinner, styles[size])} />
      <span className="visually-hidden">{label}</span>
    </span>
  )
}
