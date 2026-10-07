/**
 * The backend's closed vocabularies, and how each one should look.
 *
 * `API_CONTRACT_FOR_UI.md` is explicit that the UI branches on `code` and
 * `status`, never on prose, so the mapping lives in one table rather than in a
 * `switch` inside each screen. Two of these renderings are load-bearing and are
 * called out in the contract:
 *
 *  - `scanned_document_review` is an **info banner, not an error**. It is
 *    unconditional for any OCR-grounded document, not a judgement about the file.
 *  - A field with nothing printed comes back absent, never zero, and reads
 *    "Not on document".
 */

export type DocumentStatus =
  | 'processing'
  | 'completed'
  | 'needs_review'
  | 'document_type_mismatch'
  | 'rejected'
  | 'failed'
  | 'unsupported'

export type Tone = 'neutral' | 'success' | 'warning' | 'danger' | 'info' | 'brand'

export const STATUS_META: Record<
  string,
  { label: string; tone: Tone; help: string }
> = {
  processing: {
    label: 'Processing',
    tone: 'info',
    help: 'Still running. This view polls every 2 seconds.',
  },
  completed: {
    label: 'Completed',
    tone: 'success',
    help: 'Every required field was grounded and all validators passed.',
  },
  needs_review: {
    label: 'Needs review',
    tone: 'warning',
    help: 'Provisional. See the reasons for what a person has to confirm.',
  },
  document_type_mismatch: {
    label: 'Type mismatch',
    tone: 'danger',
    help: 'This document is not the type the schema expects, so no data was returned.',
  },
  rejected: {
    label: 'Rejected',
    tone: 'neutral',
    help: 'A reviewer rejected this extraction. It is read-only.',
  },
  failed: {
    label: 'Failed',
    tone: 'danger',
    help: 'Processing failed. The error code says why; a retry may work.',
  },
  unsupported: {
    label: 'Unsupported',
    tone: 'danger',
    help: 'This file is refused permanently. Retrying will not help.',
  },
}

export function statusMeta(status: string | null | undefined) {
  return (
    STATUS_META[status ?? ''] ?? {
      label: status ?? 'Unknown',
      tone: 'neutral' as Tone,
      help: '',
    }
  )
}

export const TERMINAL_STATUSES = new Set(
  Object.keys(STATUS_META).filter((s) => s !== 'processing'),
)

export function isTerminal(status: string | null | undefined): boolean {
  return TERMINAL_STATUSES.has(status ?? '')
}

/* --- match classes (CLAUDE.md 3.4) ------------------------------------- */

export type MatchClass =
  | 'exact'
  | 'normalized'
  | 'fuzzy_ocr'
  | 'derived'
  | 'not_found'
  | 'not_checked'

export const MATCH_META: Record<
  string,
  { label: string; tone: Tone; swatch: string; help: string }
> = {
  exact: {
    label: 'Exact',
    tone: 'success',
    swatch: 'var(--color-match-exact)',
    help: 'Found verbatim on the page.',
  },
  normalized: {
    label: 'Normalized',
    tone: 'info',
    swatch: 'var(--color-match-normalized)',
    help: 'Found after normalising separators, symbols or date format.',
  },
  derived: {
    label: 'Derived',
    tone: 'brand',
    swatch: 'var(--color-match-derived)',
    help: 'Not printed, but confirmed by deterministic code from evidence on the page.',
  },
  fuzzy_ocr: {
    label: 'Possible OCR misread',
    tone: 'warning',
    swatch: 'var(--color-match-fuzzy)',
    help: 'Within one character of a low-confidence OCR word. Check it.',
  },
  not_found: {
    label: 'Not found on page',
    tone: 'danger',
    swatch: 'var(--color-match-notfound)',
    help: 'A value was returned that could not be located on the page.',
  },
  not_checked: {
    label: 'Not on document',
    tone: 'neutral',
    swatch: 'var(--color-match-missing)',
    help: 'Nothing was printed for this field. Absent, not zero.',
  },
}

export function matchMeta(match: string | null | undefined) {
  return MATCH_META[match ?? ''] ?? MATCH_META.not_checked
}

export const GROUNDED_MATCHES = new Set(['exact', 'normalized', 'derived'])

export function isGrounded(match: string | null | undefined): boolean {
  return GROUNDED_MATCHES.has(match ?? '')
}

/* --- field status ------------------------------------------------------ */

export const FIELD_STATUS_META: Record<string, { label: string; tone: Tone }> = {
  accepted: { label: 'Accepted', tone: 'success' },
  needs_review: { label: 'Review', tone: 'warning' },
  missing: { label: 'Not on document', tone: 'neutral' },
  corrected: { label: 'Corrected', tone: 'brand' },
}

/* --- decision reasons -------------------------------------------------- */

export const SCAN_REVIEW_REASON = 'scanned_document_review'

/**
 * Carried as a *reason* on an interactive upload and as a *status* on a pipeline
 * call. The screen has to look for both: an interactive upload still shows what
 * was extracted, so it stays `needs_review` rather than returning nothing.
 */
export const TYPE_MISMATCH_REASON = 'document_type_mismatch'

/**
 * Turn a machine reason into something a reviewer can act on.
 *
 * `field_not_grounded:total` is the common shape, so the field name is pulled
 * out rather than shown raw.
 */
export function humaniseReason(reason: string): string {
  if (reason === SCAN_REVIEW_REASON) {
    return 'Scanned document — reviewed by a person before acceptance'
  }
  if (reason === TYPE_MISMATCH_REASON) {
    return 'This does not look like the document type this schema expects'
  }
  const [code, detail] = reason.split(':')
  const field = detail ? detail.replace(/_/g, ' ') : ''
  switch (code) {
    // Without a `:field` suffix these are *field-level* reasons, rendered under
    // the field they belong to, so naming it again reads as `“” is required`.
    case 'field_not_grounded':
      return field
        ? `“${field}” was returned but could not be found on the page`
        : 'Returned, but could not be found on the page'
    case 'required_field_missing':
      return field
        ? `“${field}” is required by this schema but was not found`
        : 'Required by this schema, but not found'
    case 'validation':
      return VALIDATION_LABELS[detail] ?? `Validation: ${(detail ?? '').replace(/_/g, ' ')}`
    case 'schema_invalid':
      return 'The model output did not match the schema after a repair attempt'
    case 'document_truncated':
      return 'The document was too long to send in full, so fields in the omitted text cannot be found'
    case 'warning':
      return (detail ?? '').replace(/_/g, ' ')
    default:
      return reason.replace(/[:_]/g, ' ')
  }
}

export const VALIDATION_LABELS: Record<string, string> = {
  subtotal_plus_tax_ne_total: 'Subtotal plus tax does not equal the total',
  line_sum_ne_subtotal: 'The line amounts do not sum to the subtotal',
  line_amount_mismatch: 'A row’s quantity times unit price does not equal its amount',
  tax_rate_amount_mismatch: 'The tax amount does not match the stated rate',
  tax_lines_ne_tax_amount: 'The tax lines do not sum to the tax amount',
  line_signs_disagree: 'The document mixes charges and credits',
  due_date_before_invoice_date: 'The due date falls before the invoice date',
  negative_total_on_invoice: 'An invoice with a negative total is usually a credit note',
  required_field_missing: 'A required field is missing',
}

/* --- RFC 9457 error codes ---------------------------------------------- */

export const ERROR_MESSAGES: Record<string, string> = {
  unauthenticated: 'Your session has expired. Please sign in again.',
  forbidden: 'You do not have access to that.',
  not_found: 'That no longer exists, or belongs to another project.',
  idempotency_conflict: 'That upload key was already used for a different file.',
  already_decided: 'This extraction was rejected and can no longer be corrected.',
  schema_test_run_required:
    'Run a test run on this schema version before a key can use it.',
  export_not_ready: 'The export is still being prepared.',
  file_too_large: 'That file is over the 20 MB limit.',
  empty_file: 'That file is empty.',
  corrupt_file: 'That file could not be read.',
  encrypted_pdf: 'That PDF is password protected.',
  unsupported_file_type: 'Only PDF, PNG, JPEG and TIFF files are accepted.',
  page_limit_exceeded: 'That document has too many pages.',
  invalid_request: 'Something in that request was not valid.',
  rate_limited: 'Too many requests. Try again shortly.',
  quota_exceeded: 'This project has reached its monthly quota.',
  provider_unavailable: 'The AI provider is unavailable. Try again.',
  internal: 'Something went wrong on our side.',
}

/** The shape of an RFC 9457 problem document. */
export type Problem = {
  type?: string
  title?: string
  status?: number
  detail?: string
  code?: string
  instance?: string
}

/**
 * A human message for any API failure.
 *
 * Branches on `code` and falls back to `detail`, exactly as the contract says.
 * FastAPI's own validation errors arrive with an **array** `detail`, which is a
 * different shape and is handled rather than rendered as "[object Object]".
 */
export function problemMessage(error: unknown): string {
  if (!error) return 'Something went wrong.'
  const problem = error as Problem & { detail?: unknown }

  if (Array.isArray(problem.detail)) {
    const first = problem.detail[0] as { msg?: string; loc?: string[] } | undefined
    if (first?.msg) {
      const field = first.loc?.filter((p) => p !== 'body').join('.')
      return field ? `${field}: ${first.msg}` : first.msg
    }
    return 'Some of those details were not valid.'
  }
  if (problem.code && ERROR_MESSAGES[problem.code]) return ERROR_MESSAGES[problem.code]
  if (typeof problem.detail === 'string' && problem.detail) return problem.detail
  if (problem.title) return problem.title
  if (error instanceof Error) return error.message
  return 'Something went wrong.'
}
