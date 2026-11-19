import type { NotFoundBlock } from '../../../api/types'
import { cx } from '../../../components/ui/cx'
import styles from './Notice.module.css'

/** Block `not_found`: what the user asked for is not in the catalog (RF-18). */
export function NotFoundNotice({ block }: { block: NotFoundBlock }) {
  return (
    <p className={cx(styles.notice, styles.warning)}>
      No encontramos «{block.query}» en el catálogo de MercaNova.
    </p>
  )
}
