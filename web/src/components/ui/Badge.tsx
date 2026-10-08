import type { ReactNode } from 'react'
import { cn } from '../../lib/utils'
import type { Tone } from '../../lib/status'

const TONES: Record<Tone, string> = {
  neutral:
    'bg-[var(--color-slate-100)] text-[var(--color-slate-700)] ring-[var(--color-slate-200)] ' +
    'dark:bg-[var(--color-slate-800)] dark:text-[var(--color-slate-300)] dark:ring-[var(--color-slate-700)]',
  success:
    'bg-[var(--color-success-50)] text-[var(--color-success-700)] ring-[var(--color-success-500)]/25 ' +
    'dark:bg-[var(--color-success-500)]/12 dark:text-[var(--color-success-500)] dark:ring-[var(--color-success-500)]/30',
  warning:
    'bg-[var(--color-warning-50)] text-[var(--color-warning-700)] ring-[var(--color-warning-500)]/25 ' +
    'dark:bg-[var(--color-warning-500)]/12 dark:text-[var(--color-warning-500)] dark:ring-[var(--color-warning-500)]/30',
  danger:
    'bg-[var(--color-danger-50)] text-[var(--color-danger-700)] ring-[var(--color-danger-500)]/25 ' +
    'dark:bg-[var(--color-danger-500)]/12 dark:text-[var(--color-danger-400)] dark:ring-[var(--color-danger-500)]/30',
  info:
    'bg-[var(--color-info-50)] text-[var(--color-info-700)] ring-[var(--color-info-500)]/25 ' +
    'dark:bg-[var(--color-info-500)]/12 dark:text-[var(--color-info-500)] dark:ring-[var(--color-info-500)]/30',
  brand:
    'bg-[var(--color-brand-50)] text-[var(--color-brand-700)] ring-[var(--color-brand-500)]/25 ' +
    'dark:bg-[var(--color-brand-500)]/14 dark:text-[var(--color-brand-300)] dark:ring-[var(--color-brand-500)]/30',
}

export function Badge({
  tone = 'neutral',
  children,
  className,
  icon,
  title,
}: {
  tone?: Tone
  children: ReactNode
  className?: string
  icon?: ReactNode
  title?: string
}) {
  return (
    <span
      title={title}
      className={cn(
        'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium',
        // A ring rather than a border, so the badge does not change height when
        // it sits inside a table row with its own borders.
        'ring-1 ring-inset whitespace-nowrap',
        TONES[tone],
        className,
      )}
    >
      {icon}
      {children}
    </span>
  )
}
