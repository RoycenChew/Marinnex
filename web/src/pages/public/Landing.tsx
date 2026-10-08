import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight, Check, Clock, Copy, Eye, FileWarning } from 'lucide-react'
import { DocumentFlow } from '../../components/home/DocumentFlow'
import { VerificationBadge } from '../../components/ui/VerificationBadge'
import { BRAND, GLOSSARY, HERO, JOURNEY, TRUST_FACTS, VERIFICATION } from '../../lib/copy'
import type { VerificationKey } from '../../lib/copy'
import { cn } from '../../lib/utils'

/**
 * The homepage: the blueprint's eleven sections, with the footer coming from
 * `PublicLayout`.
 *
 * Two of the blueprint's claims are not made here. It offers "invoices,
 * receipts, statements and supported financial documents"; this backend reads
 * **invoices** (C2), so the rest appears once, under a heading that says it is
 * not built yet. And its trust section lists properties the system does not
 * have; C5 leaves only the facts, which are on `/trust`.
 *
 * Nothing on this page calls an authenticated endpoint, and the numbers in it
 * come from `samples/examples.json` rather than from a copywriter.
 */

export default function Landing() {
  return (
    <>
      <Hero />
      <Problem />
      <HowItWorks />
      <Preview />
      <ReviewSection />
      <UseCases />
      <ApiSection />
      <TrustSection />
      <FirstMinutes />
      <FinalCta />
    </>
  )
}

/* ── 1. Hero ─────────────────────────────────────────────────────────── */

function Hero() {
  return (
    <section className="border-b bg-gradient-to-b from-[var(--surface-raised)] to-[var(--surface-page)]">
      <Wrap className="py-14 lg:py-20">
        <div className="grid items-center gap-10 lg:grid-cols-[minmax(0,0.78fr)_minmax(0,1fr)]">
          <div>
            <h1 className="font-[family-name:var(--font-display)] text-[clamp(2.25rem,5vw,3.5rem)] leading-[1.05] text-[var(--text-primary)]">
              {HERO.headline}
            </h1>
            <p className="mt-4 max-w-[52ch] text-base leading-relaxed text-[var(--text-secondary)]">
              {HERO.support}
            </p>
            <div className="mt-7 flex flex-wrap items-center gap-3">
              <Link
                to="/register"
                className="inline-flex h-10 items-center rounded-[var(--radius-md)] bg-[var(--accent-solid)] px-4 text-sm font-medium text-white transition-colors hover:bg-[var(--accent-solid-hover)]"
              >
                {HERO.primaryCta}
              </Link>
              <a
                href="#how-it-works"
                className="inline-flex h-10 items-center rounded-[var(--radius-md)] border px-4 text-sm font-medium text-[var(--text-primary)] transition-colors hover:bg-[var(--surface-hover)]"
              >
                {HERO.secondaryCta}
              </a>
            </div>
            <p className="mt-5 text-xs text-[var(--text-tertiary)]">
              Reads invoices today. Malaysian formats: MYR, SST, day-first dates,
              English and Malay labels.
            </p>
          </div>

          <DocumentFlow />
        </div>
      </Wrap>
    </section>
  )
}

/* ── 2. The manual-work problem ──────────────────────────────────────── */

const PROBLEM = [
  {
    icon: Clock,
    title: 'Typing, then checking the typing',
    body: 'Every invoice is read by a person and keyed into a system, then read again by someone else to catch what the first person mistyped.',
  },
  {
    icon: FileWarning,
    title: 'Tools that will not show their working',
    body: 'Most extraction tools return a value and a score. When the value is wrong, there is nothing to check it against but the original document.',
  },
  {
    icon: Eye,
    title: 'Errors that look like successes',
    body: 'A confident wrong number is worse than a blank one. It passes review because nothing about it looks unusual.',
  },
]

function Problem() {
  return (
    <section className="border-b">
      <Wrap className="py-14">
        <SectionHead
          title="Reading invoices by hand does not scale"
          lead="The work is slow, and the mistakes are quiet."
        />
        <div className="grid gap-5 sm:grid-cols-3">
          {PROBLEM.map((item) => (
            <div key={item.title}>
              <item.icon className="mb-3 h-5 w-5 text-[var(--text-brand)]" />
              <h3 className="text-sm font-semibold text-[var(--text-primary)]">
                {item.title}
              </h3>
              <p className="mt-1.5 text-sm leading-relaxed text-[var(--text-secondary)]">
                {item.body}
              </p>
            </div>
          ))}
        </div>
      </Wrap>
    </section>
  )
}

/* ── 3. How it works ─────────────────────────────────────────────────── */

const STEP_DETAIL: Record<string, string> = {
  upload:
    'A PDF with a text layer, or a photo or scan. Same file twice is recognised as the same document, so a retry never doubles your bill.',
  understand:
    'The document is classified before it is read. If you send something that is not an invoice, you are told — you do not get invoice fields filled in from a bank statement.',
  extract:
    'Values are pulled out field by field against the schema you chose, including every cell of the line-item table.',
  review:
    'Each value is matched back to the words on the page. Anything that cannot be matched, or that fails an arithmetic check, is held for a person rather than passed on.',
  select:
    'Tick the fields you actually want. That saved list is a schema, and it is versioned, so the shape of your data never changes without you.',
  use: 'Create a key, call the API, and receive the same structured result your reviewers see.',
}

function HowItWorks() {
  const [active, setActive] = useState(0)
  const step = JOURNEY[active]

  return (
    <section id="how-it-works" className="scroll-mt-16 border-b bg-[var(--surface-raised)]">
      <Wrap className="py-14">
        <SectionHead
          title="How it works"
          lead="Six steps, from a file on your desk to data in your system."
        />

        <div className="grid gap-6 md:grid-cols-[minmax(0,260px)_minmax(0,1fr)]">
          {/* A list, not a numbered carousel: it is a sequence, so the numbers
              earn their place here. */}
          <ol className="flex flex-col gap-0.5">
            {JOURNEY.map((item, index) => (
              <li key={item.key}>
                <button
                  type="button"
                  onClick={() => setActive(index)}
                  aria-current={index === active}
                  className={cn(
                    'flex w-full items-center gap-3 rounded-[var(--radius-sm)] px-3 py-2 text-left text-sm transition-colors',
                    index === active
                      ? 'bg-[var(--surface-selected)] font-medium text-[var(--text-brand)]'
                      : 'text-[var(--text-secondary)] hover:bg-[var(--surface-hover)]',
                  )}
                >
                  <span className="tabular w-4 text-xs text-[var(--text-tertiary)]">
                    {index + 1}
                  </span>
                  {item.title}
                </button>
              </li>
            ))}
          </ol>

          <div className="rounded-[var(--radius-lg)] border bg-[var(--surface-page)] p-6">
            <h3 className="font-[family-name:var(--font-display)] text-2xl text-[var(--text-primary)]">
              {step.title}
            </h3>
            <p className="mt-2 text-sm text-[var(--text-secondary)]">{step.body}</p>
            <p className="mt-4 max-w-[62ch] text-sm leading-relaxed text-[var(--text-secondary)]">
              {STEP_DETAIL[step.key]}
            </p>
          </div>
        </div>
      </Wrap>
    </section>
  )
}

/* ── 4. Product preview ──────────────────────────────────────────────── */

/** Straight from `samples/examples.json` — a real response from this backend. */
const PREVIEW_FIELDS = [
  { label: 'Invoice number', value: 'INV-2026-0417', match: 'exact' },
  { label: 'Vendor', value: 'SOUTHERN STEEL TRADING SDN BHD', match: 'exact' },
  { label: 'Invoice date', value: '2026-03-17', match: 'normalized' },
  { label: 'Subtotal', value: 'MYR 1,984.00', match: 'exact' },
  { label: 'Tax amount', value: 'MYR 158.72', match: 'exact' },
  { label: 'Total', value: 'MYR 2,142.72', match: 'exact' },
  { label: 'Bank account', value: 'Not on this document', match: 'not_checked' },
]

function Preview() {
  return (
    <section className="border-b">
      <Wrap className="py-14">
        <SectionHead
          title="What you get back"
          lead="An invoice, read into fields, each one carrying the place it came from."
        />
        <div className="overflow-hidden rounded-[var(--radius-lg)] border bg-[var(--surface-raised)]">
          <div className="border-b bg-[var(--surface-sunken)] px-4 py-2 text-xs text-[var(--text-tertiary)]">
            A real result from this system, taken from the project's own sample
            responses.
          </div>
          <ul className="divide-y">
            {PREVIEW_FIELDS.map((field) => (
              <li
                key={field.label}
                className="flex flex-wrap items-center gap-x-4 gap-y-1.5 px-4 py-3"
              >
                <span className="w-36 shrink-0 text-xs text-[var(--text-tertiary)]">
                  {field.label}
                </span>
                <span className="tabular min-w-0 flex-1 truncate text-sm text-[var(--text-primary)]">
                  {field.value}
                </span>
                <VerificationBadge match={field.match} />
              </li>
            ))}
          </ul>
        </div>
      </Wrap>
    </section>
  )
}

/* ── 5. Human review and verification ────────────────────────────────── */

const SHOWN: VerificationKey[] = ['exact', 'derived', 'fuzzy_ocr', 'not_found', 'not_checked']

function ReviewSection() {
  return (
    <section className="border-b bg-[var(--surface-raised)]">
      <Wrap className="py-14">
        <div className="grid gap-8 md:grid-cols-2">
          <div>
            <h2 className="font-[family-name:var(--font-display)] text-3xl leading-tight text-[var(--text-primary)]">
              We do not give you a score. We show you the evidence.
            </h2>
            <p className="mt-4 max-w-[54ch] text-sm leading-relaxed text-[var(--text-secondary)]">
              A percentage tells you nothing you can act on. Instead, every value
              says how it was verified against the document, and selecting it
              highlights the exact words it was read from. Arithmetic is checked
              in code, never by the model: subtotal plus tax must equal the
              total, and a rate times a base must match its amount.
            </p>
            <p className="mt-3 max-w-[54ch] text-sm leading-relaxed text-[var(--text-secondary)]">
              Anything that cannot be matched, or that fails a check, is held for
              a person. Scanned documents are always reviewed by a person before
              they are accepted.
            </p>
          </div>

          <ul className="flex flex-col gap-3 rounded-[var(--radius-lg)] border bg-[var(--surface-page)] p-5">
            {SHOWN.map((key) => (
              <li key={key} className="flex flex-col gap-1">
                <VerificationBadge match={key} />
                <p className="text-sm leading-relaxed text-[var(--text-secondary)]">
                  {VERIFICATION[key].meaning}
                </p>
              </li>
            ))}
          </ul>
        </div>
      </Wrap>
    </section>
  )
}

/* ── 6. Use cases ────────────────────────────────────────────────────── */

function UseCases() {
  return (
    <section className="border-b">
      <Wrap className="py-14">
        <SectionHead
          title="What it reads"
          lead={`${BRAND.name} is built for Malaysian financial paperwork.`}
        />
        <div className="grid gap-6 sm:grid-cols-2">
          <div className="rounded-[var(--radius-lg)] border bg-[var(--surface-raised)] p-5">
            <div className="flex items-center gap-2">
              <Check className="h-4 w-4 text-[var(--color-success-600)]" />
              <h3 className="text-sm font-semibold text-[var(--text-primary)]">
                Available now
              </h3>
            </div>
            <p className="mt-2 text-sm font-medium text-[var(--text-primary)]">
              Supplier invoices, including credit notes
            </p>
            <p className="mt-1.5 text-sm leading-relaxed text-[var(--text-secondary)]">
              Digital PDFs and scans or photos. Around 25 fields including the
              full line-item table, with SST, MYR amounts, day-first dates, and
              labels in English or Malay.
            </p>
          </div>

          {/* C2: everything else is honestly future work, and carries no date. */}
          <div className="rounded-[var(--radius-lg)] border border-dashed p-5">
            <h3 className="text-sm font-semibold text-[var(--text-secondary)]">
              Coming later
            </h3>
            <p className="mt-2 text-sm leading-relaxed text-[var(--text-secondary)]">
              Bank statements, and LHDN e-invoice files read directly without AI.
              Neither is built yet, and we are not giving them a date.
            </p>
          </div>
        </div>
      </Wrap>
    </section>
  )
}

/* ── 7. API ──────────────────────────────────────────────────────────── */

const SNIPPET = `curl -X POST https://your-host/v1/extract \\
  -H "Authorization: Bearer fdip_live_…" \\
  -F "file=@invoice.pdf" \\
  -F "schema_id=invoice" -F "schema_version=1"`

function ApiSection() {
  const [copied, setCopied] = useState(false)

  return (
    <section className="border-b bg-[var(--surface-raised)]">
      <Wrap className="py-14">
        <div className="grid gap-8 md:grid-cols-2 md:items-center">
          <div>
            <h2 className="font-[family-name:var(--font-display)] text-3xl leading-tight text-[var(--text-primary)]">
              The same result, from your own code
            </h2>
            <p className="mt-4 max-w-[54ch] text-sm leading-relaxed text-[var(--text-secondary)]">
              {GLOSSARY.schema} Pin a version, create a key, and the response
              shape is fixed. Test keys never reach the paid provider, so you can
              build against the API for nothing.
            </p>
            <Link
              to="/guide"
              className="mt-5 inline-flex items-center gap-1.5 text-sm font-medium text-[var(--text-brand)] hover:underline"
            >
              Read the guide
              <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>

          <div className="overflow-hidden rounded-[var(--radius-lg)] border bg-[var(--surface-sunken)]">
            <div className="flex items-center justify-between border-b px-3 py-2">
              <span className="text-xs text-[var(--text-tertiary)]">
                POST /v1/extract
              </span>
              <button
                type="button"
                onClick={() => {
                  void navigator.clipboard.writeText(SNIPPET)
                  setCopied(true)
                  window.setTimeout(() => setCopied(false), 1600)
                }}
                className="inline-flex items-center gap-1.5 rounded-[var(--radius-xs)] px-1.5 py-1 text-xs text-[var(--text-secondary)] hover:bg-[var(--surface-hover)]"
              >
                <Copy className="h-3 w-3" />
                {copied ? 'Copied' : 'Copy'}
              </button>
            </div>
            <pre className="overflow-x-auto p-4 text-xs leading-relaxed text-[var(--text-secondary)]">
              <code>{SNIPPET}</code>
            </pre>
          </div>
        </div>
      </Wrap>
    </section>
  )
}

/* ── 8. Trust ────────────────────────────────────────────────────────── */

function TrustSection() {
  return (
    <section className="border-b">
      <Wrap className="py-14">
        <SectionHead
          title="Where your documents go"
          lead="Stated plainly, because you are sending us your suppliers' invoices."
        />
        <div className="grid gap-5 sm:grid-cols-3">
          {TRUST_FACTS.slice(0, 3).map((fact) => (
            <div key={fact.title}>
              <h3 className="text-sm font-semibold text-[var(--text-primary)]">
                {fact.title}
              </h3>
              <p className="mt-1.5 text-sm leading-relaxed text-[var(--text-secondary)]">
                {fact.body}
              </p>
            </div>
          ))}
        </div>
        <Link
          to="/trust"
          className="mt-6 inline-flex items-center gap-1.5 text-sm font-medium text-[var(--text-brand)] hover:underline"
        >
          Everything we can tell you
          <ArrowRight className="h-3.5 w-3.5" />
        </Link>
      </Wrap>
    </section>
  )
}

/* ── 9. Your first few minutes ───────────────────────────────────────── */

const FIRST = [
  'Create an account. A project is made for you, ready to receive documents.',
  'Upload one invoice. Reading it takes under a minute for a few pages.',
  'Open the result. Select any value to see the words it was read from.',
  'Tick the fields you want, save them as a schema, and test it on a few documents.',
  'Create a key and call the API.',
]

function FirstMinutes() {
  return (
    <section className="border-b bg-[var(--surface-raised)]">
      <Wrap className="py-14">
        <SectionHead
          title="Your first few minutes"
          lead="No setup, no configuration file, no sales call."
        />
        <ol className="flex max-w-[66ch] flex-col gap-3">
          {FIRST.map((line, index) => (
            <li key={line} className="flex gap-3">
              <span className="tabular mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[var(--surface-selected)] text-xs font-medium text-[var(--text-brand)]">
                {index + 1}
              </span>
              <span className="text-sm leading-relaxed text-[var(--text-secondary)]">
                {line}
              </span>
            </li>
          ))}
        </ol>
      </Wrap>
    </section>
  )
}

/* ── 10. Final CTA ───────────────────────────────────────────────────── */

function FinalCta() {
  return (
    <section>
      <Wrap className="py-16 text-center">
        <h2 className="font-[family-name:var(--font-display)] text-[clamp(1.75rem,4vw,2.75rem)] leading-tight text-[var(--text-primary)]">
          {BRAND.tagline}
        </h2>
        <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
          <Link
            to="/register"
            className="inline-flex h-10 items-center rounded-[var(--radius-md)] bg-[var(--accent-solid)] px-4 text-sm font-medium text-white transition-colors hover:bg-[var(--accent-solid-hover)]"
          >
            {HERO.primaryCta}
          </Link>
          <Link
            to="/login"
            className="inline-flex h-10 items-center rounded-[var(--radius-md)] border px-4 text-sm font-medium text-[var(--text-primary)] transition-colors hover:bg-[var(--surface-hover)]"
          >
            Sign in
          </Link>
        </div>
      </Wrap>
    </section>
  )
}

/* ── shared ──────────────────────────────────────────────────────────── */

function Wrap({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={cn('mx-auto w-full max-w-6xl px-5', className)}>{children}</div>
  )
}

function SectionHead({ title, lead }: { title: string; lead: string }) {
  return (
    <div className="mb-8 max-w-[56ch]">
      <h2 className="font-[family-name:var(--font-display)] text-3xl leading-tight text-[var(--text-primary)]">
        {title}
      </h2>
      <p className="mt-2 text-sm leading-relaxed text-[var(--text-secondary)]">{lead}</p>
    </div>
  )
}
