import type { ReactNode } from 'react'
import { AlertCircle, LayoutGrid } from 'lucide-react'

/**
 * The frame around sign-in and registration.
 *
 * A two-column split rather than a lone centred card: the right half states what
 * the product does, which is the only thing a first-time visitor has to go on.
 * It collapses to the form alone below `lg`, because on a narrow screen the
 * marketing half would push the form below the fold.
 */
export function AuthShell({
  title,
  subtitle,
  children,
  footer,
  error,
}: {
  title: string
  subtitle: string
  children: ReactNode
  footer: ReactNode
  error?: string
}) {
  return (
    <div className="flex min-h-screen bg-[var(--surface-page)]">
      <div className="flex w-full flex-col justify-center px-6 py-10 lg:w-[46%] lg:px-14">
        <div className="mx-auto w-full max-w-sm">
          <span className="mb-7 flex items-center gap-2">
            <span className="flex h-7 w-7 items-center justify-center rounded-[var(--radius-sm)] bg-[var(--accent-solid)] text-white">
              <LayoutGrid className="h-4 w-4" />
            </span>
            <span className="text-base font-semibold tracking-[-0.02em] text-[var(--text-primary)]">
              Marinnex
            </span>
          </span>

          <h1 className="text-xl font-semibold tracking-[-0.02em] text-[var(--text-primary)]">
            {title}
          </h1>
          <p className="mt-1 mb-6 text-sm text-[var(--text-secondary)]">{subtitle}</p>

          {error && (
            <div
              role="alert"
              className="mb-4 flex items-start gap-2 rounded-[var(--radius-md)] bg-[var(--color-danger-50)] p-3 text-sm text-[var(--color-danger-700)] dark:bg-[var(--color-danger-500)]/10 dark:text-[var(--color-danger-500)]"
            >
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {children}

          <p className="mt-6 text-sm text-[var(--text-secondary)]">{footer}</p>
        </div>
      </div>

      {/* The explanatory half. Hidden below lg so the form stays above the fold. */}
      <div className="hidden flex-1 border-l bg-[var(--surface-raised)] lg:flex lg:flex-col lg:justify-center lg:px-14">
        <div className="max-w-md">
          <p className="text-lg font-medium tracking-[-0.01em] text-[var(--text-primary)]">
            Every value points back at the words it came from.
          </p>
          <p className="mt-2 text-sm text-[var(--text-secondary)]">
            FDIP reads invoices into structured JSON, then proves it: each field
            carries the page and the box it was found in, and anything the system
            could not ground goes to a person instead of into your ledger.
          </p>
          <ul className="mt-6 flex flex-col gap-3">
            {[
              ['Grounded, not guessed', 'A value that is not on the page is flagged, never quietly accepted.'],
              ['Checked arithmetic', 'Subtotal, tax and line totals are verified before anything is marked complete.'],
              ['One API', 'The same JSON from the screen and from your own pipeline, pinned to a schema version.'],
            ].map(([heading, body]) => (
              <li key={heading} className="flex gap-2.5">
                <span
                  aria-hidden
                  className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--accent-solid)]"
                />
                <span>
                  <span className="block text-sm font-medium text-[var(--text-primary)]">
                    {heading}
                  </span>
                  <span className="block text-sm text-[var(--text-secondary)]">
                    {body}
                  </span>
                </span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  )
}

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-xs font-medium text-[var(--text-secondary)]">{label}</span>
      {children}
    </label>
  )
}
