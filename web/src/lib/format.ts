/**
 * Formatting for money, dates and the API's vocabularies.
 *
 * The backend sends every decimal as a **string** on purpose: a JSON number is a
 * float on this side and `12611.70` does not survive the round trip. So nothing
 * here parses an amount into a `number` before displaying it. Amounts are
 * formatted from the string, and the only arithmetic the UI does is none.
 */

const MONEY_RE = /^-?\d+(\.\d+)?$/

/**
 * Format a decimal string as money, grouped, with the currency code.
 *
 * Returns the input untouched if it is not a plain decimal, because a value the
 * model returned as prose is a review signal and hiding it behind "—" would be
 * the wrong kind of tidy.
 */
export function formatMoney(
  value: string | number | null | undefined,
  currency?: string | null,
): string {
  if (value === null || value === undefined || value === '') return '—'
  const raw = String(value)
  if (!MONEY_RE.test(raw)) return raw

  const negative = raw.startsWith('-')
  const [whole, fraction = ''] = raw.replace('-', '').split('.')
  const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ',')
  const cents = (fraction + '00').slice(0, 2)
  const amount = `${negative ? '-' : ''}${grouped}.${cents}`
  return currency ? `${currency} ${amount}` : amount
}

/** Money without the currency code, for a column that has one in its header. */
export function formatAmount(value: string | number | null | undefined): string {
  return formatMoney(value, null)
}

/**
 * `DD/MM/YYYY`, as the UI spec requires — Malaysian documents are day-first.
 *
 * Pair every rendered date with `isoOf(value)` in a `title`, which the spec also
 * requires: day-first is unambiguous to the reader but the API's ISO string is
 * what a support conversation needs to quote.
 */
export function formatDate(value: string | null | undefined): string {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  const day = String(date.getDate()).padStart(2, '0')
  const month = String(date.getMonth() + 1).padStart(2, '0')
  return `${day}/${month}/${date.getFullYear()}`
}

/** The raw ISO value, for the tooltip beside a formatted date. */
export function isoOf(value: string | null | undefined): string | undefined {
  return value ?? undefined
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  const time = `${String(date.getHours()).padStart(2, '0')}:${String(
    date.getMinutes(),
  ).padStart(2, '0')}`
  return `${formatDate(value)} ${time}`
}

/** "3 minutes ago", for job and upload activity. */
export function formatRelative(value: string | null | undefined): string {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  const seconds = Math.round((date.getTime() - Date.now()) / 1000)
  const units: [Intl.RelativeTimeFormatUnit, number][] = [
    ['second', 60],
    ['minute', 60],
    ['hour', 24],
    ['day', 7],
    ['week', 4.348],
    ['month', 12],
    ['year', Number.POSITIVE_INFINITY],
  ]
  let amount = seconds
  for (const [unit, step] of units) {
    if (Math.abs(amount) < step) {
      return new Intl.RelativeTimeFormat('en-GB', { numeric: 'auto' }).format(
        Math.round(amount),
        unit,
      )
    }
    amount /= step
  }
  return formatDate(value)
}

/** USD cost, which is sub-cent per document and needs more than 2 places. */
export function formatCost(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  if (value === 0) return '$0.00'
  if (value < 0.01) return `$${value.toFixed(5)}`
  return `$${value.toFixed(2)}`
}

export function formatPercent(
  value: number | null | undefined,
  digits = 1,
): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return `${(value * 100).toFixed(digits)}%`
}

/** `invoice_number` -> `Invoice number`; `line_items[0].amount` -> `Amount`. */
export function humanisePath(path: string): string {
  const leaf = path.split('.').pop() ?? path
  const bare = leaf.replace(/\[\d+\]/g, '')
  return bare.charAt(0).toUpperCase() + bare.slice(1).replace(/_/g, ' ')
}

/** The row index in `line_items[3].amount`, or null for a scalar field. */
export function rowIndexOf(path: string): number | null {
  const match = path.match(/\[(\d+)\]/)
  return match ? Number(match[1]) : null
}

export function isLineItemPath(path: string): boolean {
  return path.includes('[')
}

/** `line_items[3].amount` -> `amount`. */
export function columnOf(path: string): string {
  return path.split('.').pop() ?? path
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}
