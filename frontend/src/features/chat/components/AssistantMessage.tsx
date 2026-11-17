import { Spinner } from '../../../components/ui'
import { cx } from '../../../components/ui/cx'
import type { AssistantTurn } from '../chatState'
import { ChatBlockView, type BlockActions } from './ChatBlockView'
import { ToolsUsedPanel } from './ToolsUsedPanel'
import { toolActivity } from './toolLabels'
import styles from './ChatMessage.module.css'

export interface AssistantMessageProps extends BlockActions {
  turn: AssistantTurn
  /** Only the latest answer keeps its quick replies active. */
  isLatest: boolean
}

/** An assistant answer: text written in real time, its blocks and the "Cómo lo resolví" panel. */
export function AssistantMessage({ turn, isLatest, ...actions }: AssistantMessageProps) {
  const streaming = turn.status === 'streaming'
  const waiting = streaming && (turn.activeTool !== null || turn.text === '')
  const activity = turn.activeTool ? toolActivity(turn.activeTool) : 'Pensando…'

  return (
    <article className={cx(styles.row, styles.assistantRow)} aria-label="Respuesta del asistente" aria-busy={streaming}>
      <div className={styles.content}>
        {turn.text && <p className={cx(styles.bubble, styles.assistant)}>{turn.text}</p>}
        {waiting && (
          <div className={styles.activity}>
            <Spinner size="sm" label={activity} />
            <span aria-hidden="true">{activity}</span>
          </div>
        )}
        {turn.blocks.map((block, index) => (
          <ChatBlockView key={`${block.type}-${index}`} block={block} optionsDisabled={!isLatest || streaming} {...actions} />
        ))}
        {turn.status === 'error' && turn.errorMessage && (
          <p role="alert" className={styles.error}>
            {turn.errorMessage}
          </p>
        )}
        {turn.status === 'done' && <ToolsUsedPanel tools={turn.toolsUsed} />}
      </div>
    </article>
  )
}
