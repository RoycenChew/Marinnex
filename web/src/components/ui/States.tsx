import { useEffect, useState, type ReactNode } from 'react'
import { AlertTriangle, Inbox, RefreshCw } from 'lucide-react'
import { ERROR_COPY, PROCESSING_STEPS, SUPPORT_URL } from '../../lib/copy'
import { problemMessage, type Problem } from '../../lib/status'
import { cn } from '../../lib/utils'
import { Button } from './Button'

/**
 * Empty, error and loading states.
 *
 * `FIRST_TIME_USER_PROMPT.md` is specific about all three: never a blank
 * dashboard, never `HTTP 500`, never a bare "Loading…". C9 adds the one
 * constraint the package did not know about — a developer still needs the RFC
 * 9457 `code`, so it lives in a disclosure rather than in the message.
 */

export function EmptyState({
  icon = <Inbox className="h-5 w-5" />,
  title,
  description,
  action,
  className,
}: {
  icon?: ReactNode
  title: string
  description?: string
  action?: ReactNode
  className?: string
}) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center px-6 py-14 text-center',
        className,
      )}
    >
      <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-[var(--surface-sunken)] text-[var(--text-tertiary)]">
        {icon}
      </div>
      <p className="text-base font-medium text-[var(--text-primary)]">{title}</p>
      {description && (
        <p className="mt-1 max-w-sm text-sm text-[var(--text-secondary)]">
          {description}
        </p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}

export function ErrorState({
  error,
  title = ERROR_COPY.genericTitle,
  body = ERROR_COPY.genericBody,
  onRetry,
  actions,
}: {
  error?: unknown
  title?: string
  body?: string
  onRetry?: () => void
  actions?: ReactNode
}) {
  const problem = (error ?? {}) as Problem
  const message = error ? problemMessage(error) : undefined

  return (
    <div className="flex flex-col items-center justify-center px-6 py-12 text-center">
      <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-[var(--color-danger-50)] text-[var(--color-danger-600)] dark:bg-[var(--color-danger-500)]/10">
        <AlertTriangle className="h-5 w-5" />
      </div>
      <p className="text-base font-medium text-[var(--text-primary)]">{title}</p>
      <p className="mt-1 max-w-md text-sm text-[var(--text-secondary)]">
        {message ?? body}
      </p>

      <div className="mt-4 flex flex-wrap items-center justify-center gap-2">
        {onRetry && (
          <Button variant="primary" onClick={onRetry}>
            <RefreshCw className="h-3.5 w-3.5" />
            {ERROR_COPY.retry}
          </Button>
        )}
        {actions}
        {/* C9: only when a support channel actually exists. */}
        {SUPPORT_URL && (
          <a
            href={SUPPORT_URL}
            className="inline-flex h-8 items-center rounded-[var(--radius-sm)] border px-3 text-sm font-medium text-[var(--text-secondary)] hover:bg-[var(--surface-hover)]"
          >
            Contact support
          </a>
        )}
      </div>

      {/* The friendly message is for the user; the code is for whoever they
          forward it to. Hidden, not removed. */}
      {problem.code && (
        <details className="mt-4 text-left">
          <summary className="cursor-pointer text-xs text-[var(--text-tertiary)]">
            {ERROR_COPY.detailsLabel}
          </summary>
          <pre className="mt-1.5 max-w-md overflow-x-auto rounded-[var(--radius-sm)] bg-[var(--surface-sunken)] p-2 text-xs text-[var(--text-secondary)]">
            {problem.code}
            {problem.status ? ` · HTTP ${problem.status}` : ''}
            {problem.detail ? `\n${problem.detail}` : ''}
          </pre>
        </details>
      )}
    </div>
  )
}

/**
 * Staged processing copy.
 *
 * The API exposes `job.stage`, so when it is known the message matches the real
 * stage. When it is not, the steps advance on a timer — and stop at the last one
 * rather than looping, because a message that cycles forever reads as stuck.
 */
export function LoadingState({
  stage,
  title = 'Reading your document',
}: {
  stage?: string | null
  title?: string
}) {
  const known = PROCESSING_STEPS.findIndex((s) => s.stage === stage)
  const [tick, setTick] = useState(0)

  useEffect(() => {
    if (known >= 0) return
    const timer = window.setInterval(
      () => setTick((t) => Math.min(t + 1, PROCESSING_STEPS.length - 1)),
      2600,
    )
    return () => window.clearInterval(timer)
  }, [known])

  const index = known >= 0 ? known : tick

  return (
    <div className="flex flex-col items-center justify-center gap-3 px-6 py-12 text-center">
      <ScanPulse />
      <p className="text-base font-medium text-[var(--text-primary)]">{title}</p>
      <ol className="flex flex-col gap-1.5">
        {PROCESSING_STEPS.map((step, i) => (
          <li
            key={step.stage}
            className={cn(
              'flex items-center gap-2 text-sm transition-colors duration-300',
              i < index && 'text-[var(--text-tertiary)]',
              i === index && 'text-[var(--text-primary)]',
              i > index && 'text-[var(--text-tertiary)] opacity-50',
            )}
          >
            <span
              aria-hidden
              className={cn(
                'h-1.5 w-1.5 shrink-0 rounded-full',
                i <= index
                  ? 'bg-[var(--accent-solid)]'
                  : 'bg-[var(--border-strong)]',
              )}
            />
            {step.text}
          </li>
        ))}
      </ol>
    </div>
  )
}

/** A scanning line over a page outline: the one motion that explains the wait. */
function ScanPulse() {
  return (
    <span
      aria-hidden
      className="relative block h-12 w-9 overflow-hidden rounded-[var(--radius-xs)] border bg-[var(--surface-raised)]"
    >
      {[6, 12, 18, 24, 30, 36].map((y) => (
        <span
          key={y}
          className="absolute left-1.5 h-px bg-[var(--border-strong)]"
          style={{ top: y, width: y % 12 === 0 ? 14 : 22 }}
        />
      ))}
      <span className="scanline absolute inset-x-0 h-4 bg-gradient-to-b from-transparent via-[var(--accent-solid)]/25 to-transparent" />
    </span>
  )
}
