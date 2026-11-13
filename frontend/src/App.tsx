import { NavLink, Route, Routes } from 'react-router'
import { HomePage } from './pages/HomePage'
import { UiShowcasePage } from './pages/UiShowcasePage'
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
            <NavLink to="/" end className={navLinkClass}>
              Inicio
            </NavLink>
            <NavLink to="/ui" className={navLinkClass}>
              Componentes
            </NavLink>
          </nav>
        </div>
      </header>
      <main className={styles.main}>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/ui" element={<UiShowcasePage />} />
        </Routes>
      </main>
    </div>
  )
}
