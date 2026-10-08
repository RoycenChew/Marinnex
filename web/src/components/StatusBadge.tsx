import { AlertCircle, Check, CircleDashed, Loader2, Slash, XCircle } from 'lucide-react'
import { Badge } from './ui/Badge'
import { statusMeta } from '../lib/status'

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
/* `MatchBadge` lived here. It is gone: `ui/VerificationBadge` is now the one
   place a match class becomes words, so the workspace, the homepage and the
   tour cannot drift into three different vocabularies for the same six
   states. */
