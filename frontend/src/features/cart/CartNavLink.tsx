import { NavLink } from 'react-router'
import { paths } from '../../routes/paths'
import { useCart } from './useCart'
import styles from './CartNavLink.module.css'

/** Header link to the cart with the number of units in it. */
export function CartNavLink() {
  const count = useCart().cart?.item_count ?? 0
  const label = count > 0 ? `Carrito, ${count === 1 ? '1 producto' : `${count} productos`}` : 'Carrito'

  return (
    <NavLink
      to={paths.cart}
      aria-label={label}
      className={({ isActive }) => (isActive ? `${styles.link} ${styles.active}` : styles.link)}
    >
      Carrito
      {count > 0 && (
        <span aria-hidden="true" className={styles.count}>
          {count}
        </span>
      )}
    </NavLink>
  )
}
