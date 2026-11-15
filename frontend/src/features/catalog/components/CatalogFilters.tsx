import { useId, useState, type FormEvent } from 'react'
import type { CategoryList, ProductListParams, ProductSort } from '../../../api/types'
import { Button, Card, Input } from '../../../components/ui'
import styles from './CatalogFilters.module.css'

export interface CatalogFiltersProps {
  value: ProductListParams
  categories: CategoryList
  onChange: (next: ProductListParams) => void
  onClear: () => void
}

const SORT_OPTIONS: { value: ProductSort | ''; label: string }[] = [
  { value: '', label: 'Relevancia' },
  { value: 'price_asc', label: 'Menor precio' },
  { value: 'price_desc', label: 'Mayor precio' },
  { value: 'rating', label: 'Mejor calificados' },
]

interface Draft {
  q: string
  min: string
  max: string
}

const draftFrom = (value: ProductListParams): Draft => ({
  q: value.q ?? '',
  min: value.min_price?.toString() ?? '',
  max: value.max_price?.toString() ?? '',
})

const toNumber = (text: string): number | undefined => (text.trim() === '' ? undefined : Number(text))

/**
 * Catalog filters. Selects and the stock checkbox apply right away; the text search and the
 * price range apply when the form is submitted ("Aplicar" or Enter).
 * Remount it (with `key`) when `value` changes from outside, so the text fields follow.
 */
export function CatalogFilters({ value, categories, onChange, onClear }: CatalogFiltersProps) {
  const [draft, setDraft] = useState<Draft>(() => draftFrom(value))
  const categoryId = useId()
  const subcategoryId = useId()
  const sortId = useId()

  const min = toNumber(draft.min)
  const max = toNumber(draft.max)
  const priceError =
    min !== undefined && max !== undefined && min > max ? 'Tiene que ser mayor que el mínimo.' : undefined

  // Applies the typed text and prices too, so a select change does not drop them.
  const apply = (changes: Partial<ProductListParams>) => {
    if (priceError) return
    onChange({
      ...value,
      q: draft.q.trim() || undefined,
      min_price: min,
      max_price: max,
      ...changes,
    })
  }

  const submit = (event: FormEvent) => {
    event.preventDefault()
    apply({})
  }

  const subcategories = categories.find((c) => c.category === value.category)?.subcategories ?? []

  return (
    <Card padding="md">
      <form className={styles.form} onSubmit={submit} role="search" aria-label="Filtrar productos">
        <Input
          label="Buscar"
          type="search"
          placeholder="Nombre, marca o descripción"
          value={draft.q}
          onChange={(event) => setDraft({ ...draft, q: event.target.value })}
        />

        <div className={styles.field}>
          <label htmlFor={categoryId} className={styles.label}>
            Categoría
          </label>
          <select
            id={categoryId}
            className={styles.select}
            value={value.category ?? ''}
            onChange={(event) =>
              apply({ category: event.target.value || undefined, subcategory: undefined })
            }
          >
            <option value="">Todas</option>
            {categories.map((group) => (
              <option key={group.category} value={group.category}>
                {group.category}
              </option>
            ))}
          </select>
        </div>

        <div className={styles.field}>
          <label htmlFor={subcategoryId} className={styles.label}>
            Subcategoría
          </label>
          <select
            id={subcategoryId}
            className={styles.select}
            value={value.subcategory ?? ''}
            disabled={subcategories.length === 0}
            onChange={(event) => apply({ subcategory: event.target.value || undefined })}
          >
            <option value="">Todas</option>
            {subcategories.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </div>

        <fieldset className={styles.priceRange}>
          <legend className={styles.label}>Precio (USD)</legend>
          <div className={styles.priceInputs}>
            <Input
              label="Mínimo"
              type="number"
              inputMode="decimal"
              min={0}
              value={draft.min}
              onChange={(event) => setDraft({ ...draft, min: event.target.value })}
            />
            <Input
              label="Máximo"
              type="number"
              inputMode="decimal"
              min={0}
              value={draft.max}
              error={priceError}
              onChange={(event) => setDraft({ ...draft, max: event.target.value })}
            />
          </div>
        </fieldset>

        <label className={styles.checkbox}>
          <input
            type="checkbox"
            checked={value.in_stock === true}
            onChange={(event) => apply({ in_stock: event.target.checked || undefined })}
          />
          Solo con stock
        </label>

        <div className={styles.field}>
          <label htmlFor={sortId} className={styles.label}>
            Ordenar por
          </label>
          <select
            id={sortId}
            className={styles.select}
            value={value.sort ?? ''}
            onChange={(event) => apply({ sort: (event.target.value || undefined) as ProductSort | undefined })}
          >
            {SORT_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>

        <div className={styles.actions}>
          <Button type="submit" disabled={priceError !== undefined}>
            Aplicar
          </Button>
          <Button variant="ghost" onClick={onClear}>
            Limpiar filtros
          </Button>
        </div>
      </form>
    </Card>
  )
}
