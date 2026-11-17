import type { ReactNode } from 'react'
import type { Order } from '../../../api/types'
import { Button, Modal } from '../../../components/ui'
import { OrderSummary } from './OrderSummary'
import styles from './ConfirmOrderDialog.module.css'

export interface ConfirmOrderDialogProps {
  order: Order
  warehouseName?: string
  /** A request is in flight: both buttons are disabled and the dialog cannot be dismissed. */
  pending: boolean
  /** Message or content shown in an alert region (for example a price change or a network error). */
  problem?: ReactNode
  /** Set to false when confirming cannot work anymore (for example after PRICE_CHANGED). */
  canConfirm?: boolean
  /** Only called from the explicit "Confirmar compra" click. */
  onConfirm: () => void
  /** "Cancelar compra", the close button and Escape all mean this. */
  onCancel: () => void
}

/** Explicit purchase confirmation (RF-12). The backdrop never closes it. */
export function ConfirmOrderDialog({
  order,
  warehouseName,
  pending,
  problem,
  canConfirm = true,
  onConfirm,
  onCancel,
}: ConfirmOrderDialogProps) {
  return (
    <Modal
      open
      title="Confirmá tu compra"
      closeOnBackdropClick={false}
      onClose={() => {
        if (!pending) onCancel()
      }}
      footer={
        <>
          <Button variant="secondary" disabled={pending} onClick={onCancel}>
            Cancelar compra
          </Button>
          {canConfirm && (
            <Button disabled={pending} onClick={onConfirm}>
              Confirmar compra
            </Button>
          )}
        </>
      }
    >
      <div className={styles.content}>
        {problem && (
          <div role="alert" className={styles.problem}>
            {problem}
          </div>
        )}
        <OrderSummary order={order} warehouseName={warehouseName} />
      </div>
    </Modal>
  )
}
