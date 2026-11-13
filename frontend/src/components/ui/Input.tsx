import { useId, type InputHTMLAttributes } from 'react'
import { cx } from './cx'
import styles from './Input.module.css'

export interface InputProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'id'> {
  /** Visible label. Required so every field is accessible. */
  label: string
  /** Error message shown under the field. Marks the field as invalid. */
  error?: string
  /** Helper text shown under the field when there is no error. */
  hint?: string
  id?: string
}

export function Input({ label, error, hint, id, className, required, ...rest }: InputProps) {
  const generatedId = useId()
  const inputId = id ?? generatedId
  const messageId = `${inputId}-message`
  const message = error ?? hint

  return (
    <div className={cx(styles.field, className)}>
      <label htmlFor={inputId} className={styles.label}>
        {label}
        {required && (
          <span aria-hidden="true" className={styles.required}>
            {' *'}
          </span>
        )}
      </label>
      <input
        {...rest}
        id={inputId}
        required={required}
        aria-invalid={error ? true : undefined}
        aria-describedby={message ? messageId : undefined}
        className={cx(styles.input, error && styles.invalid)}
      />
      {message && (
        <p id={messageId} className={error ? styles.error : styles.hint}>
          {message}
        </p>
      )}
    </div>
  )
}
