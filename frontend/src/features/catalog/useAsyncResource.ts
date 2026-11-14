import { useCallback, useEffect, useState } from 'react'
import { ApiRequestError } from '../../api/http'

const FALLBACK_ERROR = 'Ocurrió un error inesperado. Intentá de nuevo en unos minutos.'

export type AsyncResource<T> =
  | { status: 'loading' }
  | { status: 'error'; message: string; code: string | null }
  | { status: 'success'; data: T }

/**
 * Loads data whenever `key` changes, cancelling the previous request so a slow response never
 * overwrites a newer one. Errors become a Spanish message ready to show.
 */
export function useAsyncResource<T>(
  key: string,
  load: (signal: AbortSignal) => Promise<T>,
): AsyncResource<T> & { retry: () => void } {
  const [state, setState] = useState<AsyncResource<T>>({ status: 'loading' })
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    setState({ status: 'loading' })
    load(controller.signal).then(
      (data) => {
        if (!controller.signal.aborted) setState({ status: 'success', data })
      },
      (error: unknown) => {
        if (controller.signal.aborted) return
        setState(
          error instanceof ApiRequestError
            ? { status: 'error', message: error.message, code: error.code }
            : { status: 'error', message: FALLBACK_ERROR, code: null },
        )
      },
    )
    return () => controller.abort()
    // `load` is recreated on every render; `key` identifies what it loads.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, attempt])

  const retry = useCallback(() => setAttempt((n) => n + 1), [])
  return { ...state, retry }
}
