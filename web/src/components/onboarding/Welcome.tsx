import { ArrowRight, Upload } from 'lucide-react'
import { BRAND } from '../../lib/copy'

/**
 * The first screen of an empty account.
 *
 * It replaces the dashboard rather than sitting above it: a brand-new user has
 * no documents, so four zeroed KPI cards and an empty table teach them nothing
 * and make the product look broken. Once a document exists, this is gone for
 * good.
 *
 * The four steps are the product in one screen, written for someone who has
 * never heard of OCR, extraction or a schema.
 */

const STEPS = [
  {
    title: 'Upload a document',
    body: 'An invoice, as a PDF, a scan or a photo from your phone.',
  },
  {
    title: 'We read it',
    body: 'Values are found field by field, including the whole line-item table.',
  },
  {
    title: 'You check it',
    body: 'Every value shows the words on the page it came from. Anything uncertain is held for you.',
  },
  {
    title: 'Use your data',
    body: 'Export a spreadsheet, or call the API from your own system.',
  },
]

export function Welcome({
  onUpload,
  onTour,
}: {
  onUpload: () => void
  onTour: () => void
}) {
  return (
    <section className="rounded-[var(--radius-lg)] border bg-[var(--surface-raised)] p-8">
      <h1 className="font-[family-name:var(--font-display)] text-3xl leading-tight text-[var(--text-primary)]">
        Welcome to {BRAND.name}
      </h1>
      <p className="mt-2 max-w-[56ch] text-sm leading-relaxed text-[var(--text-secondary)]">
        Let's turn your first invoice into information you can use. It takes
        about a minute, and there is nothing to set up first.
      </p>

      <ol className="mt-7 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
        {STEPS.map((step, index) => (
          <li key={step.title}>
            <span className="tabular flex h-6 w-6 items-center justify-center rounded-full bg-[var(--surface-selected)] text-xs font-medium text-[var(--text-brand)]">
              {index + 1}
            </span>
            <h2 className="mt-2.5 text-sm font-semibold text-[var(--text-primary)]">
              {step.title}
            </h2>
            <p className="mt-1 text-sm leading-relaxed text-[var(--text-secondary)]">
              {step.body}
            </p>
          </li>
        ))}
      </ol>

      <div className="mt-8 flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={onUpload}
          className="inline-flex h-10 items-center gap-2 rounded-[var(--radius-md)] bg-[var(--accent-solid)] px-4 text-sm font-medium text-white transition-colors hover:bg-[var(--accent-solid-hover)]"
        >
          <Upload className="h-4 w-4" />
          Upload my first document
        </button>
        <button
          type="button"
          onClick={onTour}
          className="inline-flex h-10 items-center gap-1.5 rounded-[var(--radius-md)] border px-4 text-sm font-medium text-[var(--text-primary)] transition-colors hover:bg-[var(--surface-hover)]"
        >
          Take a 1-minute tour
          <ArrowRight className="h-3.5 w-3.5" />
        </button>
      </div>
    </section>
  )
}
