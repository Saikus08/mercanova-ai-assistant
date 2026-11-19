import type { ToolUsage } from '../../../api/types'
import { toolSummary } from './toolLabels'
import styles from './ToolsUsedPanel.module.css'

const formatArg = (value: unknown): string => (typeof value === 'string' ? value : JSON.stringify(value))

/** Collapsible "Cómo lo resolví" panel: the tools the assistant ran for this answer, in order. */
export function ToolsUsedPanel({ tools }: { tools: ToolUsage[] }) {
  if (tools.length === 0) return null
  return (
    <details className={styles.panel}>
      <summary className={styles.summary}>Cómo lo resolví</summary>
      <ol className={styles.list}>
        {tools.map((tool, index) => {
          const args = Object.entries(tool.args ?? {})
          return (
            <li key={`${tool.name}-${index}`} className={styles.item}>
              <span>{toolSummary(tool.name)}</span> <code className={styles.code}>{tool.name}</code>
              {args.length > 0 && (
                <dl className={styles.args}>
                  {args.map(([key, value]) => (
                    <div key={key} className={styles.arg}>
                      <dt>{key}</dt>
                      <dd>{formatArg(value)}</dd>
                    </div>
                  ))}
                </dl>
              )}
            </li>
          )
        })}
      </ol>
    </details>
  )
}
