import type { HTMLAttributes } from 'react'
import { cx } from './cx'
import styles from './Badge.module.css'

export type BadgeVariant = 'neutral' | 'success' | 'warning' | 'danger'

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant
}

export function Badge({ variant = 'neutral', className, children, ...rest }: BadgeProps) {
  return (
    <span {...rest} className={cx(styles.badge, styles[variant], className)}>
      {children}
    </span>
  )
}
