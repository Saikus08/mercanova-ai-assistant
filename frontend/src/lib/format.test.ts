import { describe, expect, it } from 'vitest'
import { formatDateTime } from './format'

describe('formatDateTime', () => {
  it('formats an ISO instant as date and time in es-UY', () => {
    // 22:05 UTC is 19:05 in Montevideo (UTC-3), the store's time zone.
    expect(formatDateTime('2026-11-12T22:05:00Z')).toBe('12/11/2026, 19:05')
  })

  it('does not depend on the machine time zone', () => {
    expect(formatDateTime('2026-11-13T02:30:00Z')).toBe('12/11/2026, 23:30')
  })
})
