import { getSessionId } from './session'
import type { ApiError, ApiErrorCode } from './types'

const NETWORK_ERROR_MESSAGE = 'No pudimos conectarnos con la tienda. Revisá tu conexión e intentá de nuevo.'
const UNEXPECTED_ERROR_MESSAGE = 'Ocurrió un error inesperado. Intentá de nuevo en unos minutos.'

/** Error thrown by the API client. `message` is Spanish and can be shown to the user as is. */
export class ApiRequestError extends Error {
  readonly code: ApiErrorCode | 'NETWORK_ERROR'
  readonly status: number | null
  readonly details?: Record<string, unknown>

  constructor(
    code: ApiErrorCode | 'NETWORK_ERROR',
    message: string,
    status: number | null,
    details?: Record<string, unknown>,
  ) {
    super(message)
    this.name = 'ApiRequestError'
    this.code = code
    this.status = status
    this.details = details
  }
}

export type QueryValue = string | number | boolean | undefined | null

export function buildQuery(params: Record<string, QueryValue>): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === '') continue
    search.set(key, String(value))
  }
  const query = search.toString()
  return query ? `?${query}` : ''
}

function isApiError(body: unknown): body is ApiError {
  if (typeof body !== 'object' || body === null || !('error' in body)) return false
  const error = (body as { error: unknown }).error
  return (
    typeof error === 'object' &&
    error !== null &&
    typeof (error as { code?: unknown }).code === 'string' &&
    typeof (error as { message?: unknown }).message === 'string'
  )
}

/** GET a JSON resource under `/api`, with the session header and contract error handling. */
export async function apiGet<T>(path: string, signal?: AbortSignal): Promise<T> {
  let response: Response
  try {
    response = await fetch(`/api${path}`, {
      headers: { Accept: 'application/json', 'X-Session-Id': getSessionId() },
      signal,
    })
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === 'AbortError') throw cause
    throw new ApiRequestError('NETWORK_ERROR', NETWORK_ERROR_MESSAGE, null)
  }

  const body: unknown = await response.json().catch(() => null)

  if (!response.ok) {
    if (isApiError(body)) {
      const { code, message, details } = body.error
      throw new ApiRequestError(code, message, response.status, details)
    }
    throw new ApiRequestError('INTERNAL_ERROR', UNEXPECTED_ERROR_MESSAGE, response.status)
  }

  return body as T
}
