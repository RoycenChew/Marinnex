import {
  AlertTriangle,
  Calculator,
  CircleHelp,
  Eye,
  Minus,
  ShieldCheck,
} from 'lucide-react'
import type { ReactNode } from 'react'
import { SCAN_QUALITY, VERIFICATION, scanQuality } from '../../lib/copy'
import type { VerificationKey } from '../../lib/copy'
import { cn } from '../../lib/utils'
import { Badge } from './Badge'
import type { Tone } from '../../lib/status'

/**
 * C1 — how a value was verified. **Never a percentage.**
 *
 * The backend has no calibrated per-field confidence. It knows how the value was
 * matched against the document, and that is a better thing to show: "Found on
 * page" is checkable, "96% confident" is not. Showing a number here would be an
 * accuracy claim the system cannot support.
 *
 * Every state carries an icon *and* text, so the meaning never depends on colour
 * alone — which matters on the page overlay, where colour is all there is.
 */

const ICONS: Record<VerificationKey, typeof ShieldCheck> = {
  exact: ShieldCheck,
  normalized: ShieldCheck,
  derived: Calculator,
  fuzzy_ocr: Eye,
  not_found: AlertTriangle,
  not_checked: Minus,
}

function keyOf(match: string | null | undefined): VerificationKey {
  return (match && match in VERIFICATION ? match : 'not_checked') as VerificationKey
}

export function VerificationBadge({
  match,
  ocrConfidence,
  showHint = false,
  className,
}: {
  match: string | null | undefined
  /** Only present on OCR evidence; a text-layer field has none. */
  ocrConfidence?: number | null
  showHint?: boolean
  className?: string
}) {
  const key = keyOf(match)
  const state = VERIFICATION[key]
  const Icon = ICONS[key]

  return (
    <span className={cn('inline-flex flex-wrap items-center gap-1', className)}>
      <Badge
        tone={state.tone as Tone}
        title={showHint ? undefined : state.meaning}
        icon={<Icon className="h-3 w-3" />}
      >
        {state.label}
      </Badge>
      {/* Scan quality rides along only where the evidence actually came from a
          scan. On a text-layer field there is nothing to measure. */}
      {typeof ocrConfidence === 'number' && (
        <Badge tone="neutral" title={SCAN_QUALITY.hint}>
          {SCAN_QUALITY[scanQuality(ocrConfidence)]}
        </Badge>
      )}
    </span>
  )
}

/** The plain-English meaning, for a hint or a legend. */
export function verificationMeaning(match: string | null | undefined): string {
  return VERIFICATION[keyOf(match)].meaning
}

export function verificationLabel(match: string | null | undefined): string {
  return VERIFICATION[keyOf(match)].label
}

/**
 * A "?" that explains one term. Used beside anything a first-time user would not
 * be expected to know — confidence, schema, API key.
 */
export function HelpHint({
  children,
  label = 'What does this mean?',
}: {
  children: ReactNode
  label?: string
}) {
  return (
    <span className="group relative inline-flex">
      <button
        type="button"
        aria-label={label}
        className="rounded-full p-0.5 text-[var(--text-tertiary)] hover:text-[var(--text-primary)]"
      >
        <CircleHelp className="h-3.5 w-3.5" />
      </button>
      <span
        role="tooltip"
        className={cn(
          'pointer-events-none absolute bottom-full left-1/2 z-50 mb-1.5 w-60 -translate-x-1/2',
          'rounded-[var(--radius-md)] border bg-[var(--surface-overlay)] px-2.5 py-2',
          'text-xs leading-relaxed text-[var(--text-secondary)] shadow-md',
          'opacity-0 transition-opacity duration-150',
          'group-hover:opacity-100 group-focus-within:opacity-100',
        )}
      >
        {children}
      </span>
    </span>
  )
}
