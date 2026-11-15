import { NavLink } from 'react-router'
import { AppRoutes } from './routes/routes'
import { paths } from './routes/paths'
import styles from './App.module.css'

const navLinkClass = ({ isActive }: { isActive: boolean }) =>
  isActive ? `${styles.navLink} ${styles.active}` : styles.navLink

export function App() {
  return (
    <div className={styles.shell}>
      <header className={styles.header}>
        <div className={styles.headerInner}>
          <span className={styles.brand}>MercaNova</span>
          <nav aria-label="Principal" className={styles.nav}>
            <NavLink to={paths.catalog} end className={navLinkClass}>
              Catálogo
            </NavLink>
            <NavLink to={paths.ui} className={navLinkClass}>
              Componentes
            </NavLink>
          </nav>
        </div>
      </header>
      <main className={styles.main}>
        <AppRoutes />
      </main>
    </div>
  )
}
