import { describe, expect, it } from 'vitest'
import { applyTokens, color, space, toCssVariables } from './tokens'

describe('design tokens', () => {
  it('maps every token to a kebab-case CSS custom property', () => {
    const variables = toCssVariables()

    expect(variables['--color-primary']).toBe(color.primary)
    expect(variables['--color-primary-hover']).toBe(color.primaryHover)
    expect(variables['--space-4']).toBe(space[4])
    expect(variables['--font-size-2xl']).toBeDefined()
    expect(variables['--size-control-height-md']).toBeDefined()
  })

  it('applies the variables to the document root', () => {
    applyTokens()

    expect(document.documentElement.style.getPropertyValue('--color-primary')).toBe(
      color.primary,
    )
  })
})
