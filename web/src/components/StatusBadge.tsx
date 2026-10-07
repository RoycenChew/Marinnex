import { AlertCircle, Check, CircleDashed, Loader2, Slash, XCircle } from 'lucide-react'
import { Badge } from './ui/Badge'
import { matchMeta, statusMeta } from '../lib/status'

const ICONS: Record<string, typeof Check> = {
  completed: Check,
  needs_review: AlertCircle,
  processing: Loader2,
  document_type_mismatch: XCircle,
  failed: XCircle,
  unsupported: Slash,
  rejected: CircleDashed,
}

/**
 * A document or extraction status.
 *
 * The error code goes in the tooltip rather than the label, as the UI spec asks:
 * `unsupported` is what the user needs to see, `encrypted_pdf` is what they need
 * when they ask why.
 */
export function StatusBadge({
  status,
  code,
}: {
  status: string | null | undefined
  code?: string | null
}) {
  const meta = statusMeta(status)
  const Icon = ICONS[status ?? '']
  return (
    <Badge
      tone={meta.tone}
      title={code ? `${meta.help} (${code})` : meta.help}
      icon={
        Icon ? (
          <Icon
            className={status === 'processing' ? 'h-3 w-3 animate-spin' : 'h-3 w-3'}
          />
        ) : undefined
      }
    >
      {meta.label}
    </Badge>
  )
}

/** A field's grounding class, with its meaning in the tooltip. */
export function MatchBadge({ match }: { match: string | null | undefined }) {
  const meta = matchMeta(match)
  return (
    <Badge tone={meta.tone} title={meta.help}>
      <span
        aria-hidden
        className="h-1.5 w-1.5 rounded-full"
        style={{ backgroundColor: meta.swatch }}
      />
      {meta.label}
    </Badge>
  )
}
