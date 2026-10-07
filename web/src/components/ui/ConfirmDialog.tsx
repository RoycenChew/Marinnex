import * as AlertDialog from '@radix-ui/react-alert-dialog'
import type { ReactNode } from 'react'
import { Button } from './Button'

/**
 * Confirmation for anything that destroys data.
 *
 * Deleting a document cascades to every extraction, correction and decision made
 * on it, so the copy says what is actually lost rather than "Are you sure?".
 */
export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel = 'Delete',
  destructive = true,
  loading,
  onConfirm,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  description: ReactNode
  confirmLabel?: string
  destructive?: boolean
  loading?: boolean
  onConfirm: () => void
}) {
  return (
    <AlertDialog.Root open={open} onOpenChange={onOpenChange}>
      <AlertDialog.Portal>
        <AlertDialog.Overlay className="fixed inset-0 z-50 bg-[var(--color-slate-950)]/40 backdrop-blur-[2px]" />
        <AlertDialog.Content
          className="fixed top-1/2 left-1/2 z-50 w-[min(28rem,calc(100vw-2rem))] -translate-x-1/2 -translate-y-1/2 rounded-[var(--radius-lg)] border bg-[var(--surface-overlay)] p-5 shadow-lg"
        >
          <AlertDialog.Title className="text-base font-semibold text-[var(--text-primary)]">
            {title}
          </AlertDialog.Title>
          <AlertDialog.Description className="mt-1.5 text-sm text-[var(--text-secondary)]">
            {description}
          </AlertDialog.Description>
          <div className="mt-5 flex justify-end gap-2">
            <AlertDialog.Cancel asChild>
              <Button variant="secondary">Cancel</Button>
            </AlertDialog.Cancel>
            <Button
              variant={destructive ? 'danger' : 'primary'}
              loading={loading}
              onClick={onConfirm}
            >
              {confirmLabel}
            </Button>
          </div>
        </AlertDialog.Content>
      </AlertDialog.Portal>
    </AlertDialog.Root>
  )
}
