import type { HTMLAttributes } from 'react'
import { cx } from './cx'
import styles from './Card.module.css'

export type CardPadding = 'none' | 'md' | 'lg'

export interface CardProps extends HTMLAttributes<HTMLDivElement> {
  padding?: CardPadding
}

export function Card({ padding = 'md', className, children, ...rest }: CardProps) {
  return (
    <div {...rest} className={cx(styles.card, styles[padding], className)}>
      {children}
    </div>
  )
}
