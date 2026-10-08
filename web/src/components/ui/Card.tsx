import type { ReactNode } from 'react'
import { cn } from '../../lib/utils'

/**
 * A raised surface.
 *
 * Elevation comes from a border first and a shadow second. On a dense data
 * screen a drop shadow under every card turns into visual noise, and the border
 * is what actually communicates "this is a separate region".
 */
export function Card({
  children,
  className,
  padded = true,
}: {
  children: ReactNode
  className?: string
  padded?: boolean
}) {
  return (
    <div
      className={cn(
        'rounded-[var(--radius-lg)] border bg-[var(--surface-raised)] shadow-xs',
        padded && 'p-4',
        className,
      )}
    >
      {children}
    </div>
  )
}

export function CardHeader({
  title,
  description,
  action,
  className,
}: {
  title: ReactNode
  description?: ReactNode
  action?: ReactNode
  className?: string
}) {
  return (
    <div className={cn('flex items-start justify-between gap-4', className)}>
      <div className="min-w-0">
        <h2 className="text-lg font-semibold tracking-[-0.01em] text-[var(--text-primary)]">
          {title}
        </h2>
        {description && (
          <p className="mt-0.5 text-sm text-[var(--text-secondary)]">{description}</p>
        )}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  )
}

/**
 * A single headline metric.
 *
 * The label sits above the number in sentence case, not tracked-out capitals:
 * these are read in a row of four, and four shouted labels compete with the
 * figures they are supposed to introduce.
 */
export function StatCard({
  label,
  value,
  hint,
  icon,
  tone = 'default',
  loading,
}: {
  label: string
  value: ReactNode
  hint?: ReactNode
  icon?: ReactNode
  tone?: 'default' | 'warning' | 'success'
  loading?: boolean
}) {
  return (
    <div className="rounded-[var(--radius-lg)] border bg-[var(--surface-raised)] p-4 shadow-xs">
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm font-medium text-[var(--text-secondary)]">{label}</span>
        {icon && <span className="text-[var(--text-tertiary)]">{icon}</span>}
      </div>
      {loading ? (
        <div className="mt-2 h-8 w-24 animate-pulse rounded-[var(--radius-sm)] bg-[var(--surface-sunken)]" />
      ) : (
        <div
          className={cn(
            'tabular mt-1.5 text-2xl font-semibold tracking-[-0.02em]',
            tone === 'warning' && 'text-[var(--color-warning-600)]',
            tone === 'success' && 'text-[var(--color-success-600)]',
            tone === 'default' && 'text-[var(--text-primary)]',
          )}
        >
          {value}
        </div>
      )}
      {hint && (
        <div className="mt-1 text-xs text-[var(--text-tertiary)]">{hint}</div>
      )}
    </div>
  )
}
