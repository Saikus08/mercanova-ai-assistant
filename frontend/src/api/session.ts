const STORAGE_KEY = 'mercanova.session_id'

/**
 * Anonymous session id sent in `X-Session-Id` (see docs/api-contract.md, "Sesión del usuario").
 * Generated once and kept in localStorage so the cart and orders survive a reload.
 */
export function getSessionId(storage: Storage = window.localStorage): string {
  const existing = storage.getItem(STORAGE_KEY)
  if (existing) return existing

  const created = crypto.randomUUID()
  storage.setItem(STORAGE_KEY, created)
  return created
}
