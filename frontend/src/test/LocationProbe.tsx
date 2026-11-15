import { useLocation } from 'react-router'

/** Prints the current URL so tests can assert on navigation and filters. */
export function LocationProbe() {
  const location = useLocation()
  return <output data-testid="location">{location.pathname + location.search}</output>
}
