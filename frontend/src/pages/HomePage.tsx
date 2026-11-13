import { Card } from '../components/ui'
import styles from './HomePage.module.css'

/** Placeholder until the catalog screen is built. */
export function HomePage() {
  return (
    <Card padding="lg" className={styles.placeholder}>
      <h1 className={styles.title}>Catálogo próximamente</h1>
      <p className={styles.text}>
        Acá vas a poder buscar productos y conversar con el asistente de compras.
      </p>
    </Card>
  )
}
