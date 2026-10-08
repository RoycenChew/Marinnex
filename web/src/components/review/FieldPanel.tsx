import { useMemo } from 'react'
import { Check, CheckCheck, Pencil, X } from 'lucide-react'
import type { Extraction, FieldEntry } from '../../api/types'
import { columnOf, formatAmount, humanisePath, rowIndexOf } from '../../lib/format'
import { humaniseReason, matchMeta } from '../../lib/status'
import { cn } from '../../lib/utils'
import { Button } from '../ui/Button'
import { VerificationBadge } from '../ui/VerificationBadge'

/**
 * Which group a field belongs to.
 *
 * Header / Totals / Line items, as the UI spec asks. Totals are separated because
 * they are the numbers a reviewer checks first and the ones the arithmetic
 * validators talk about.
 */
const TOTAL_PATHS = new Set([
  'subtotal',
  'discount_amount',
  'tax_rate',
  'tax_amount',
  'rounding_adjustment',
  'total',
  'currency',
])

export type Group = { key: string; label: string; paths: string[] }

export function groupFields(fields: Record<string, FieldEntry>): Group[] {
  const header: string[] = []
  const totals: string[] = []
  const lineItems: string[] = []
  for (const path of Object.keys(fields)) {
    if (path.includes('[')) lineItems.push(path)
    else if (TOTAL_PATHS.has(path)) totals.push(path)
    else header.push(path)
  }
  const order = (list: string[]) => list.sort((a, b) => a.localeCompare(b))
  return [
    { key: 'header', label: 'Header', paths: order(header) },
    { key: 'totals', label: 'Totals', paths: order(totals) },
    { key: 'lineItems', label: 'Line items', paths: order(lineItems) },
  ].filter((group) => group.paths.length > 0)
}

const MONEY_COLUMNS = new Set(['amount', 'unit_price', 'subtotal', 'total', 'tax_amount'])

function displayValue(path: string, entry: FieldEntry) {
  if (entry.value === null || entry.value === undefined || entry.value === '') {
    return null
  }
  const column = columnOf(path)
  if (MONEY_COLUMNS.has(column) && typeof entry.value === 'string') {
    return formatAmount(entry.value)
  }
  if (typeof entry.value === 'object') return JSON.stringify(entry.value)
  return String(entry.value)
}

/** One scalar field: value, verification state, reasons, inline edit. */
export function FieldRow({
  path,
  entry,
  selected,
  editing,
  draft,
  checked,
  onSelect,
  onEdit,
  onDraft,
  onCommit,
  onCancel,
  onCheck,
}: {
  path: string
  entry: FieldEntry
  selected: boolean
  editing: boolean
  draft: string
  /** Marked checked by this reviewer, in this sitting. See `onCheck`. */
  checked?: boolean
  onSelect: () => void
  onEdit: () => void
  onDraft: (value: string) => void
  onCommit: () => void
  onCancel: () => void
  onCheck?: () => void
}) {
  const value = displayValue(path, entry)
  const meta = matchMeta(entry.match)
  const absent = entry.status === 'missing' || value === null
  const needsReview = entry.status === 'needs_review'
  /* OCR confidence rides on the evidence, and only scans have it. Taking the
     lowest across a value's words means a run is as trustworthy as its worst
     word, which is the honest reading. */
  const ocrConfidence = useMemo(() => {
    const values = (entry.evidence ?? [])
      .map((item) => item?.ocr_confidence)
      .filter((n): n is number => typeof n === 'number')
    return values.length > 0 ? Math.min(...values) : undefined
  }, [entry.evidence])

  return (
    <div
      id={`field-${path}`}
      onClick={onSelect}
      className={cn(
        'group cursor-pointer border-l-2 px-3 py-2 transition-colors duration-100',
        selected
          ? 'border-l-[var(--accent-solid)] bg-[var(--surface-selected)]'
          : 'border-l-transparent hover:bg-[var(--surface-hover)]',
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <span className="text-xs font-medium text-[var(--text-secondary)]">
          {humanisePath(path)}
        </span>
        <span className="flex shrink-0 items-center gap-1">
          {!absent && (
            <VerificationBadge match={entry.match} ocrConfidence={ocrConfidence} />
          )}
          {/* A toggle, not a one-way button: a reviewer who marks the wrong row,
              or wants a second look, needs it back. The mark is recorded on the
              server as an audit event, so it survives a reload — it changes no
              status, and the document-level Approve is still the decision. */}
          {needsReview && onCheck && !editing && (
            <button
              type="button"
              aria-pressed={!!checked}
              aria-label={
                checked
                  ? `${humanisePath(path)} is checked. Undo`
                  : `Mark ${humanisePath(path)} as checked`
              }
              title={checked ? 'Checked. Select to undo.' : 'Mark as checked'}
              onClick={(e) => {
                e.stopPropagation()
                onCheck()
              }}
              className={cn(
                'inline-flex items-center gap-0.5 rounded-[var(--radius-xs)] px-1 py-0.5 text-[11px]',
                checked
                  ? 'text-[var(--color-success-600)]'
                  : 'text-[var(--text-tertiary)] opacity-0 group-hover:opacity-100 focus-visible:opacity-100 hover:text-[var(--text-primary)]',
              )}
            >
              <CheckCheck className="h-3 w-3" />
              {checked ? 'Checked' : 'Mark checked'}
            </button>
          )}
          {!editing && (
            <Button
              size="icon"
              variant="ghost"
              aria-label={`Edit ${humanisePath(path)}`}
              className="h-5 w-5 opacity-0 group-hover:opacity-100 focus-visible:opacity-100"
              onClick={(e) => {
                e.stopPropagation()
                onEdit()
              }}
            >
              <Pencil className="h-3 w-3" />
            </Button>
          )}
        </span>
      </div>

      {editing ? (
        <div className="mt-1 flex items-center gap-1">
          <input
            autoFocus
            value={draft}
            onChange={(e) => onDraft(e.target.value)}
            onClick={(e) => e.stopPropagation()}
            onKeyDown={(e) => {
              if (e.key === 'Enter') onCommit()
              if (e.key === 'Escape') onCancel()
            }}
            className="w-full rounded-[var(--radius-sm)] border bg-[var(--surface-raised)] px-2 py-1 text-sm text-[var(--text-primary)] outline-none focus:border-[var(--border-focus)]"
          />
          <Button size="icon" variant="ghost" aria-label="Apply" onClick={(e) => { e.stopPropagation(); onCommit() }}>
            <Check className="h-3.5 w-3.5 text-[var(--color-success-600)]" />
          </Button>
          <Button size="icon" variant="ghost" aria-label="Cancel" onClick={(e) => { e.stopPropagation(); onCancel() }}>
            <X className="h-3.5 w-3.5" />
          </Button>
        </div>
      ) : (
        <div
          className={cn(
            'mt-0.5 text-sm',
            absent
              ? 'text-[var(--text-tertiary)] italic'
              : 'tabular text-[var(--text-primary)]',
          )}
        >
          {/* An absent field is absent, never zero. The contract is explicit. */}
          {absent ? 'Not on document' : value}
        </div>
      )}

      {entry.reasons.length > 0 && (
        <ul className="mt-1 flex flex-col gap-0.5">
          {entry.reasons.map((reason) => (
            <li
              key={reason}
              className="flex items-start gap-1 text-xs text-[var(--text-secondary)]"
            >
              <span
                aria-hidden
                className="mt-1 h-1 w-1 shrink-0 rounded-full"
                style={{ backgroundColor: meta.swatch }}
              />
              {humaniseReason(reason)}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

/** The line-item table, one row per index, each cell its own field. */
export function LineItemGrid({
  extraction,
  selectedPath,
  onSelectPath,
}: {
  extraction: Extraction
  selectedPath: string | null
  onSelectPath: (path: string) => void
}) {
  const { rows, columns } = useMemo(() => {
    const byRow = new Map<number, Record<string, string>>()
    const columnSet = new Set<string>()
    for (const path of Object.keys(extraction.fields)) {
      const index = rowIndexOf(path)
      if (index === null) continue
      const column = columnOf(path)
      columnSet.add(column)
      const existing = byRow.get(index) ?? {}
      existing[column] = path
      byRow.set(index, existing)
    }
    /*
     * A column every row leaves empty is noise: the tax-code column on an
     * invoice that states no tax codes was a dash repeated down the table,
     * which reads as data until you look twice. If the schema asked for it and
     * the document does not show it, the honest table simply has no such
     * column — the field is still listed in full under its group.
     */
    const hasValue = (column: string) =>
      [...byRow.values()].some((cells) => {
        const entry = cells[column] ? extraction.fields[cells[column]] : undefined
        return entry != null && entry.value !== null && entry.value !== ''
      })
    const preferred = ['description', 'quantity', 'unit_price', 'amount', 'tax_code']
    const ordered = [
      ...preferred.filter((c) => columnSet.has(c)),
      ...[...columnSet].filter((c) => !preferred.includes(c)).sort(),
    ].filter(hasValue)
    return {
      rows: [...byRow.entries()].sort((a, b) => a[0] - b[0]),
      columns: ordered,
    }
  }, [extraction.fields])

  if (rows.length === 0) {
    return (
      <p className="px-3 py-4 text-sm text-[var(--text-tertiary)]">
        No line items on this document.
      </p>
    )
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="border-b bg-[var(--surface-sunken)]">
            <th className="w-8 px-2 py-1.5 text-right text-xs font-medium text-[var(--text-tertiary)]">
              #
            </th>
            {columns.map((column) => (
              <th
                key={column}
                className={cn(
                  'px-2 py-1.5 text-xs font-medium text-[var(--text-secondary)]',
                  MONEY_COLUMNS.has(column) || column === 'quantity'
                    ? 'text-right'
                    : 'text-left',
                )}
              >
                {humanisePath(column)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y">
          {rows.map(([index, cells]) => (
            <tr key={index}>
              <td className="tabular px-2 py-1.5 text-right text-xs text-[var(--text-tertiary)]">
                {index + 1}
              </td>
              {columns.map((column) => {
                const path = cells[column]
                const entry = path ? extraction.fields[path] : undefined
                const numeric = MONEY_COLUMNS.has(column) || column === 'quantity'
                const selected = path === selectedPath
                return (
                  <td
                    key={column}
                    onClick={() => path && onSelectPath(path)}
                    title={entry ? matchMeta(entry.match).help : undefined}
                    className={cn(
                      'cursor-pointer px-2 py-1.5',
                      numeric && 'tabular text-right',
                      selected
                        ? 'bg-[var(--surface-selected)]'
                        : 'hover:bg-[var(--surface-hover)]',
                    )}
                  >
                    <span className="flex items-center gap-1.5" style={numeric ? { justifyContent: 'flex-end' } : undefined}>
                      {entry && (
                        <span
                          aria-hidden
                          className="h-1.5 w-1.5 shrink-0 rounded-full"
                          style={{ backgroundColor: matchMeta(entry.match).swatch }}
                        />
                      )}
                      <span className="truncate text-[var(--text-primary)]">
                        {/* Blank, not a dash: a surviving column can still have
                            a gap in one row, and an empty cell says "nothing
                            here" without looking like a value. */}
                        {entry ? displayValue(path, entry) : null}
                      </span>
                    </span>
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
