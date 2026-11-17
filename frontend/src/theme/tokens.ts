/**
 * Design tokens: the ONLY place in the app where raw colors, sizes and fonts live.
 *
 * Components never use these values directly in CSS. `applyTokens()` exposes every
 * token as a CSS custom property on `:root`, so CSS modules write `var(--color-primary)`,
 * `var(--space-4)`, etc. Use the typed objects below only when a value is needed in
 * TypeScript (for example, breakpoints inside a `matchMedia` call).
 *
 * Naming: `<group>.<key>` becomes `--<group>-<key>` in kebab-case.
 * Example: `color.primaryHover` -> `--color-primary-hover`, `space[4]` -> `--space-4`.
 */

const palette = {
  indigo50: '#eef2ff',
  indigo100: '#e0e7ff',
  indigo600: '#4f46e5',
  indigo700: '#4338ca',
  green50: '#f0fdf4',
  green100: '#dcfce7',
  green700: '#15803d',
  amber50: '#fffbeb',
  amber100: '#fef3c7',
  amber700: '#b45309',
  red50: '#fef2f2',
  red100: '#fee2e2',
  red600: '#dc2626',
  red700: '#b91c1c',
  white: '#ffffff',
  gray50: '#f9fafb',
  gray100: '#f3f4f6',
  gray200: '#e5e7eb',
  gray300: '#d1d5db',
  gray400: '#9ca3af',
  gray500: '#6b7280',
  gray600: '#4b5563',
  gray700: '#374151',
  gray800: '#1f2937',
  gray900: '#111827',
} as const

/** Semantic colors. Components use these names, never the palette above. */
export const color = {
  primary: palette.indigo600,
  primaryHover: palette.indigo700,
  primarySubtle: palette.indigo50,
  primaryBorder: palette.indigo100,
  onPrimary: palette.white,

  success: palette.green700,
  successSubtle: palette.green100,
  successSurface: palette.green50,

  warning: palette.amber700,
  warningSubtle: palette.amber100,
  warningSurface: palette.amber50,

  danger: palette.red600,
  dangerHover: palette.red700,
  dangerSubtle: palette.red100,
  dangerSurface: palette.red50,
  onDanger: palette.white,

  background: palette.gray50,
  surface: palette.white,
  surfaceMuted: palette.gray100,
  surfaceHover: palette.gray200,
  border: palette.gray200,
  borderStrong: palette.gray300,
  disabled: palette.gray400,

  text: palette.gray900,
  textSecondary: palette.gray700,
  textMuted: palette.gray500,

  focusRing: palette.indigo600,
  overlay: 'rgba(17, 24, 39, 0.5)',
} as const

/** Spacing scale on a 4px grid. */
export const space = {
  0: '0',
  1: '4px',
  2: '8px',
  3: '12px',
  4: '16px',
  5: '20px',
  6: '24px',
  8: '32px',
  10: '40px',
  12: '48px',
  16: '64px',
} as const

export const radius = {
  sm: '4px',
  md: '8px',
  lg: '12px',
  full: '9999px',
} as const

export const font = {
  family: "'Inter', system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif",
  familyMono: "ui-monospace, 'SFMono-Regular', Menlo, Consolas, monospace",
} as const

export const fontSize = {
  xs: '12px',
  sm: '14px',
  md: '16px',
  lg: '18px',
  xl: '20px',
  '2xl': '24px',
  '3xl': '30px',
} as const

export const fontWeight = {
  regular: '400',
  medium: '500',
  semibold: '600',
  bold: '700',
} as const

export const lineHeight = {
  tight: '1.25',
  normal: '1.5',
} as const

export const shadow = {
  sm: '0 1px 2px rgba(17, 24, 39, 0.06)',
  md: '0 4px 12px rgba(17, 24, 39, 0.08)',
  lg: '0 16px 40px rgba(17, 24, 39, 0.18)',
} as const

/** Fixed sizes for controls and overlays. */
export const size = {
  borderWidth: '1px',
  focusRingWidth: '2px',
  controlHeightSm: '32px',
  controlHeightMd: '40px',
  iconSm: '16px',
  iconMd: '24px',
  iconLg: '40px',
  modalWidth: '520px',
  contentMaxWidth: '1200px',
  /** Catalog layout: filters column, minimum width of the results column and of a product card. */
  filtersWidth: '260px',
  resultsMinWidth: '480px',
  productCardMinWidth: '220px',
  /** Product image in the detail screen. */
  detailImageWidth: '480px',
  /** Cart layout: product thumbnail, quantity number between the stepper buttons, summary column. */
  cartImage: '80px',
  quantityDisplayWidth: '32px',
  cartSummaryWidth: '320px',
  /** Checkout: width of the form column. */
  checkoutWidth: '640px',
  /** Chat: width of the conversation column and maximum width of a text bubble. */
  chatWidth: '960px',
  chatBubbleMaxWidth: '640px',
} as const

export const zIndex = {
  header: '10',
  modal: '100',
} as const

export const motion = {
  durationFast: '120ms',
  durationSlow: '800ms',
} as const

/**
 * Breakpoints (min-width). CSS media queries cannot read custom properties, so use
 * these from TypeScript (for example with `window.matchMedia`).
 */
export const breakpoint = {
  sm: '640px',
  md: '768px',
  lg: '1024px',
  xl: '1280px',
} as const

export const tokens = {
  color,
  space,
  radius,
  font,
  fontSize,
  fontWeight,
  lineHeight,
  shadow,
  size,
  zIndex,
  motion,
  breakpoint,
} as const

export type Tokens = typeof tokens

const toKebab = (value: string): string =>
  value.replace(/([a-z0-9])([A-Z])/g, '$1-$2').toLowerCase()

/** Flattens the token tree into `{ '--color-primary': '#4f46e5', ... }`. */
export function toCssVariables(source: Tokens = tokens): Record<string, string> {
  const variables: Record<string, string> = {}
  for (const [group, values] of Object.entries(source)) {
    for (const [key, value] of Object.entries(values as Record<string, string>)) {
      variables[`--${toKebab(group)}-${toKebab(key)}`] = value
    }
  }
  return variables
}

/** Writes every token as a CSS custom property on the given element (`:root` by default). */
export function applyTokens(target: HTMLElement = document.documentElement): void {
  for (const [name, value] of Object.entries(toCssVariables())) {
    target.style.setProperty(name, value)
  }
}
