import { useEffect, useRef, useState } from 'react'
import { ArrowRight, FileText, Upload } from 'lucide-react'
import { VerificationBadge } from '../ui/VerificationBadge'
import { cn } from '../../lib/utils'

/**
 * The hero: a miniature run of the real product, Document → Verified data → API.
 *
 * Ported from the package's `marinnex-document-flow.html`, with three changes
 * the master prompt requires.
 *
 * **C1.** The prototype's Scene 5 showed "96% confidence" and "68% confidence".
 * No such number exists: the backend reports a match class, not a calibrated
 * probability. Inventing one on the homepage would be an accuracy claim before
 * the visitor has seen a single document. Scene 5 shows verification states
 * through the same `VerificationBadge` the workspace uses, so the homepage
 * promises exactly what the product delivers.
 *
 * **C3.** Every value here is lifted from `samples/examples.json` — a real
 * response from this backend. Money is a decimal string beside an ISO currency,
 * as the API returns it, not a JSON float.
 *
 * **Motion.** It pauses off screen, holds a static final frame under
 * `prefers-reduced-motion`, and never takes the pointer: `aria-hidden` with
 * `pointer-events-none`, because it is an illustration of the copy beside it,
 * not content of its own.
 */

/** From `GET /v1/documents/{id}/analysis` in samples/examples.json. */
const INVOICE = {
  vendor: 'SOUTHERN STEEL TRADING SDN BHD',
  number: 'INV-2026-0417',
  date: '17/03/2026',
  po: 'PO-88213',
  subtotal: '1,984.00',
  taxRate: '8',
  tax: '158.72',
  total: '2,142.72',
  currency: 'MYR',
}

const FIELDS = [
  { label: 'Invoice number', value: INVOICE.number, match: 'exact' },
  { label: 'Vendor', value: INVOICE.vendor, match: 'exact' },
  { label: 'Invoice date', value: '2026-03-17', match: 'normalized' },
  { label: 'Subtotal', value: `${INVOICE.currency} ${INVOICE.subtotal}`, match: 'exact' },
  { label: 'Tax (SST 8%)', value: `${INVOICE.currency} ${INVOICE.tax}`, match: 'fuzzy_ocr' },
  { label: 'Total', value: `${INVOICE.currency} ${INVOICE.total}`, match: 'exact' },
] as const

const SCENES = [
  { key: 'document', ms: 2000, caption: 'A financial document' },
  { key: 'upload', ms: 1700, caption: 'Upload your document' },
  { key: 'processing', ms: 3200, caption: 'Reading the document' },
  { key: 'extract', ms: 3000, caption: 'Finding the information' },
  { key: 'verify', ms: 3600, caption: 'Showing where each value came from' },
  { key: 'review', ms: 3000, caption: 'Review what matters' },
  { key: 'data', ms: 3000, caption: 'Structured data' },
  { key: 'api', ms: 2800, caption: 'Ready to use' },
] as const

type SceneKey = (typeof SCENES)[number]['key']

const LAST = SCENES.length - 1

const STATUS_LINES = [
  'Reading document…',
  'Identifying financial fields…',
  'Validating extracted values…',
]

/** C3: the real contract — decimal strings, ISO dates, ISO currency. */
const RESPONSE = `{
  "status": "needs_review",
  "document_type": "invoice",
  "currency": "MYR",
  "data": {
    "invoice_number": "${INVOICE.number}",
    "invoice_date": "2026-03-17",
    "vendor_name": "SOUTHERN STEEL…",
    "subtotal": "1984.00",
    "tax_amount": "158.72",
    "total": "2142.72"
  }
}`

export function DocumentFlow() {
  const [scene, setScene] = useState(0)
  const containerRef = useRef<HTMLDivElement>(null)
  const visibleRef = useRef(true)
  const [still, setStill] = useState(false)

  // Reduced motion holds the last frame: the story's conclusion, which is also
  // the most informative single image of the eight.
  useEffect(() => {
    const query = window.matchMedia('(prefers-reduced-motion: reduce)')
    const apply = () => {
      setStill(query.matches)
      if (query.matches) setScene(LAST)
    }
    apply()
    query.addEventListener('change', apply)
    return () => query.removeEventListener('change', apply)
  }, [])

  // Off screen, the timer stops rather than running the loop into an empty
  // viewport and landing the visitor mid-scene when they scroll back.
  useEffect(() => {
    const node = containerRef.current
    if (!node) return
    const observer = new IntersectionObserver(
      ([entry]) => {
        visibleRef.current = entry.isIntersecting
      },
      { threshold: 0.25 },
    )
    observer.observe(node)
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    if (still) return
    const tick = () => {
      if (visibleRef.current) setScene((current) => (current + 1) % SCENES.length)
      timer = window.setTimeout(tick, visibleRef.current ? SCENES[scene].ms : 600)
    }
    let timer = window.setTimeout(tick, SCENES[scene].ms)
    return () => window.clearTimeout(timer)
  }, [scene, still])

  const at = (key: SceneKey) => SCENES.findIndex((s) => s.key === key)
  const current = SCENES[scene].key

  return (
    <div
      ref={containerRef}
      aria-hidden
      className="pointer-events-none select-none"
    >
      <div className="grid gap-4 md:grid-cols-2">
        {/* ── Left: the document ─────────────────────────────────────── */}
        <Panel label="Financial document">
          <div
            className={cn(
              'relative overflow-hidden rounded-[var(--radius-md)] border bg-white p-5 text-[13px]',
              'transition-all duration-500 ease-out dark:bg-[var(--surface-raised)]',
              current === 'document' && !still
                ? 'translate-y-1 opacity-90'
                : 'translate-y-0 opacity-100',
            )}
          >
            <div className="mb-3 flex items-start justify-between border-b pb-3">
              <div>
                <div className="font-semibold text-[var(--text-primary)]">
                  {INVOICE.vendor}
                </div>
                <div className="text-[11px] text-[var(--text-tertiary)]">
                  Tax invoice · {INVOICE.po}
                </div>
              </div>
              <div className="text-right text-[11px] text-[var(--text-tertiary)]">
                <div>{INVOICE.number}</div>
                <div>{INVOICE.date}</div>
              </div>
            </div>

            <DocRow label="Hex bolt stainless M8 HBS-1000" value="500.00" />
            <DocRow label="Steel plate 6mm SP-6000" value="1,484.00" />
            <DocRow label="Subtotal" value={INVOICE.subtotal} />
            <DocRow
              label={`SST ${INVOICE.taxRate}%`}
              value={INVOICE.tax}
              highlighted={current === 'review'}
            />
            <DocRow label="Total (MYR)" value={INVOICE.total} strong />

            {/* Scene 3: one restrained pass, not a looping light show. */}
            {current === 'processing' && !still && (
              <span
                className="scanline-hero absolute inset-x-[8%] top-0 h-px bg-[var(--accent-solid)]"
                style={{ boxShadow: '0 0 12px var(--accent-solid)' }}
              />
            )}

            {/* Scene 2: the document is placed into the product. */}
            {current === 'upload' && !still && (
              <div className="absolute inset-0 grid place-items-center bg-[var(--surface-page)]/80">
                <span className="flex items-center gap-2 rounded-[var(--radius-md)] border border-dashed border-[var(--accent-solid)] bg-[var(--surface-raised)] px-3 py-2 text-xs font-medium text-[var(--text-brand)]">
                  <Upload className="h-3.5 w-3.5" />
                  Upload your document
                </span>
              </div>
            )}
          </div>
        </Panel>

        {/* ── Right: what the product makes of it ────────────────────── */}
        <Panel label={SCENES[scene].caption}>
          <div className="min-h-[278px]">
            {(current === 'document' || current === 'upload') && (
              <Centred>
                <FileText className="h-6 w-6 text-[var(--text-tertiary)]" />
                <p className="text-sm text-[var(--text-secondary)]">
                  Drop in a PDF or a photo of an invoice.
                </p>
              </Centred>
            )}

            {current === 'processing' && (
              <ul className="flex flex-col gap-2.5 pt-2">
                {STATUS_LINES.map((line, index) => (
                  <li
                    key={line}
                    className="flex items-center gap-2 text-sm text-[var(--text-secondary)] opacity-0"
                    style={{
                      animation: still
                        ? undefined
                        : `flow-in 400ms ease-out ${index * 700}ms forwards`,
                      opacity: still ? 1 : undefined,
                    }}
                  >
                    <span className="h-1.5 w-1.5 rounded-full bg-[var(--accent-solid)]" />
                    {line}
                  </li>
                ))}
              </ul>
            )}

            {(current === 'extract' || current === 'verify' || current === 'review') && (
              <ul className="flex flex-col divide-y">
                {FIELDS.map((field, index) => {
                  const isTax = field.match === 'fuzzy_ocr'
                  return (
                    <li
                      key={field.label}
                      className={cn(
                        'flex flex-wrap items-center justify-between gap-x-3 gap-y-1 py-2',
                        current === 'review' &&
                          isTax &&
                          '-mx-2 rounded-[var(--radius-sm)] bg-[var(--surface-selected)] px-2',
                      )}
                      style={{
                        animation:
                          still || current !== 'extract'
                            ? undefined
                            : `flow-in 350ms ease-out ${index * 260}ms backwards`,
                      }}
                    >
                      <span className="text-xs text-[var(--text-tertiary)]">
                        {field.label}
                      </span>
                      <span className="tabular text-sm font-medium text-[var(--text-primary)]">
                        {field.value.length > 22
                          ? `${field.value.slice(0, 20)}…`
                          : field.value}
                      </span>
                      {/* C1: the same badge the workspace shows. No number. */}
                      {scene >= at('verify') && (
                        <VerificationBadge match={field.match} className="basis-full" />
                      )}
                    </li>
                  )
                })}
              </ul>
            )}

            {current === 'data' && (
              <pre className="overflow-hidden rounded-[var(--radius-md)] bg-[var(--surface-sunken)] p-3 text-[11px] leading-relaxed text-[var(--text-secondary)]">
                <code>{RESPONSE}</code>
              </pre>
            )}

            {current === 'api' && (
              <Centred>
                <div className="flex items-center gap-2.5 text-sm text-[var(--text-secondary)]">
                  <span className="rounded-[var(--radius-sm)] border px-2 py-1 text-xs">
                    Marinnex Lab
                  </span>
                  <ArrowRight className="h-4 w-4 text-[var(--text-tertiary)]" />
                  <span className="rounded-[var(--radius-sm)] border px-2 py-1 text-xs">
                    Your system
                  </span>
                </div>
                <p className="text-sm text-[var(--text-secondary)]">
                  The same data, from your own code.
                </p>
              </Centred>
            )}
          </div>

          {current === 'review' && (
            <p className="mt-3 border-t pt-3 text-sm text-[var(--text-secondary)]">
              One value needs a second look. The rest are already checked.
            </p>
          )}
        </Panel>
      </div>

      {/* Progress, and the only place the eight scenes are named. */}
      <ol className="mt-3 flex items-center justify-center gap-1.5">
        {SCENES.map((s, index) => (
          <li
            key={s.key}
            className={cn(
              'h-1 rounded-full transition-all duration-300',
              index === scene
                ? 'w-6 bg-[var(--accent-solid)]'
                : 'w-1.5 bg-[var(--border-default)]',
            )}
          />
        ))}
      </ol>
    </div>
  )
}

function Panel({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="rounded-[var(--radius-lg)] border bg-[var(--surface-raised)] p-4 shadow-xs">
      <div className="mb-3 text-[11px] font-medium tracking-wide text-[var(--text-tertiary)]">
        {label}
      </div>
      {children}
    </div>
  )
}

function Centred({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-full min-h-[278px] flex-col items-center justify-center gap-2 text-center">
      {children}
    </div>
  )
}

function DocRow({
  label,
  value,
  strong,
  highlighted,
}: {
  label: string
  value: string
  strong?: boolean
  highlighted?: boolean
}) {
  return (
    <div
      className={cn(
        'flex items-center justify-between gap-3 border-b py-1.5 last:border-0',
        'transition-colors duration-300',
        highlighted && '-mx-1.5 rounded-[var(--radius-xs)] bg-[var(--color-warning-50)] px-1.5',
        strong && 'font-semibold',
      )}
    >
      <span className="truncate text-[var(--text-secondary)]">{label}</span>
      <span className="tabular shrink-0 text-[var(--text-primary)]">{value}</span>
    </div>
  )
}
