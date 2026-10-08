/**
 * Mock-only enrichment of the captured responses.
 *
 * `samples/examples.json` is captured from a real backend run, which makes it the
 * right source of truth — but two of its entries were trimmed when they were
 * captured (the analysis body keeps three `fields` and says so in
 * `_fields_note`), and it has no entry at all for the page image, which is binary.
 *
 * So mock mode would render a review screen with three fields and no page. This
 * file fills those two holes **for mock mode only**. Every value here is taken
 * from the same invoice the samples were captured from
 * (`fdip/samples/invoice_digital.pdf`), so the mocked screen shows what the real
 * one shows.
 *
 * Nothing in this file is imported by application code.
 */

import type { Evidence, Extraction, FieldEntry } from '../api/types'

type Spec = {
  path: string
  value: string | null
  match: FieldEntry['match']
  bbox?: [number, number, number, number]
  reasons?: string[]
  /** Set to make the evidence OCR, with this minimum word confidence. */
  ocr?: number
}

/** Boxes are in PDF points against a 595 x 842 page, as the real API returns. */
const HEADER: Spec[] = [
  { path: 'document_type', value: 'invoice', match: 'normalized', bbox: [40, 108, 120, 119] },
  { path: 'invoice_number', value: 'INV-2026-0417', match: 'exact', bbox: [146, 121, 232, 132] },
  { path: 'invoice_date', value: '2026-03-17', match: 'normalized', bbox: [330, 121, 400, 132] },
  // Two fields are deliberately imperfect, so the review path is exercised:
  // one word the scanner struggled with, and one value with nowhere on the page
  // to point at. Without them every mock document is clean and the review queue
  // never appears.
  {
    path: 'due_date',
    value: '2026-04-16',
    match: 'fuzzy_ocr',
    bbox: [330, 134, 400, 145],
    ocr: 0.61,
    reasons: ['possible_ocr_misread'],
  },
  { path: 'po_number', value: 'PO-88213', match: 'exact', bbox: [120, 134, 180, 145] },
  { path: 'do_number', value: null, match: 'not_checked' },
  { path: 'vendor_name', value: 'SOUTHERN STEEL TRADING SDN BHD', match: 'exact', bbox: [40, 56, 290, 68] },
  { path: 'vendor_registration_no', value: '201901234567', match: 'exact', bbox: [96, 69, 170, 80] },
  { path: 'vendor_tax_id', value: 'C12345678901', match: 'exact', bbox: [215, 69, 295, 80] },
  { path: 'vendor_address', value: '12 Jalan Perindustrian 3, 81100 Johor Bahru', match: 'exact', bbox: [40, 82, 300, 93] },
  { path: 'vendor_contact', value: null, match: 'not_checked' },
  { path: 'buyer_name', value: 'Harapan Engineering Sdn Bhd', match: 'exact', bbox: [86, 160, 270, 171] },
  { path: 'buyer_tax_id', value: null, match: 'not_checked' },
  { path: 'buyer_address', value: null, match: 'not_checked' },
  { path: 'amount_in_words', value: null, match: 'not_checked' },
  { path: 'payment_terms', value: '30 days nett', match: 'not_found', reasons: ['value_not_found_on_page'] },
  { path: 'bank_account', value: null, match: 'not_checked' },
]

const TOTALS: Spec[] = [
  { path: 'currency', value: 'MYR', match: 'derived', bbox: [404, 251, 424, 262] },
  { path: 'subtotal', value: '1984.00', match: 'normalized', bbox: [404, 251, 470, 262] },
  { path: 'discount_amount', value: null, match: 'not_checked' },
  { path: 'tax_rate', value: '8', match: 'exact', bbox: [40, 264, 70, 275] },
  { path: 'tax_amount', value: '158.72', match: 'normalized', bbox: [414, 264, 470, 275] },
  { path: 'rounding_adjustment', value: null, match: 'not_checked' },
  { path: 'total', value: '2142.72', match: 'normalized', bbox: [404, 277, 470, 288] },
]

const LINE_ITEMS: { description: string; quantity: string; unit_price: string; amount: string; top: number }[] = [
  { description: 'Hex bolt stainless M8 HBS-1000', quantity: '40', unit_price: '12.50', amount: '500.00', top: 199 },
  { description: 'Flange nut zinc plated FNZ-220', quantity: '120', unit_price: '3.20', amount: '384.00', top: 212 },
  { description: 'Steel plate 6mm SP-6000', quantity: '5', unit_price: '220.00', amount: '1100.00', top: 225 },
]

function evidence(spec: Spec): Evidence[] {
  if (!spec.bbox) return []
  return [
    {
      page: 1,
      bbox: spec.bbox,
      source: spec.ocr === undefined ? 'text_layer' : 'ocr',
      ocr_confidence: spec.ocr ?? null,
    },
  ]
}

function entry(spec: Spec): FieldEntry {
  const absent = spec.value === null
  return {
    value: spec.value,
    raw_text: absent ? null : spec.value,
    status: absent
      ? 'missing'
      : spec.match === 'not_found' || spec.match === 'fuzzy_ocr'
        ? 'needs_review'
        : 'accepted',
    match: spec.match,
    evidence: evidence(spec),
    reasons: spec.reasons ?? [],
  }
}

export function buildAnalysis(base: Partial<Extraction>): Extraction {
  const fields: Record<string, FieldEntry> = {}
  for (const spec of [...HEADER, ...TOTALS]) fields[spec.path] = entry(spec)

  LINE_ITEMS.forEach((row, index) => {
    const columns: [string, string, number, number][] = [
      ['description', row.description, 40, 250],
      ['quantity', row.quantity, 300, 330],
      ['unit_price', row.unit_price, 350, 410],
      ['amount', row.amount, 420, 470],
    ]
    for (const [column, value, x0, x1] of columns) {
      fields[`line_items[${index}].${column}`] = entry({
        path: column,
        value,
        match: 'exact',
        bbox: [x0, row.top, x1, row.top + 11],
      })
    }
    fields[`line_items[${index}].tax_code`] = entry({
      path: 'tax_code',
      value: null,
      match: 'not_checked',
    })
  })

  const data: Record<string, unknown> = {}
  for (const spec of [...HEADER, ...TOTALS]) data[spec.path] = spec.value
  data.line_items = LINE_ITEMS.map((row) => ({
    description: row.description,
    quantity: row.quantity,
    unit_price: row.unit_price,
    amount: row.amount,
  }))

  return {
    extraction_id: 'ext_1m4an4fjhp7x4a2tz',
    document_id: 'doc_1m4an4f05hm4wn0vd',
    version: 1,
    document_type: 'invoice',
    schema: { id: 'invoice', version: 1 },
    currency: 'MYR',
    pipeline_version: '2026.10.1',
    created_at: '2026-10-07T07:44:12',
    validation: [],
    suggested_fields: Object.entries(fields)
      .filter(([, value]) => ['exact', 'normalized', 'derived'].includes(value.match))
      .map(([path]) => path)
      .sort(),
    ...base,
    data,
    fields,
    // After `base`, not before: the captured response says "completed", and it
    // was captured from a document whose fields were all clean. Two of these
    // are not, so the status has to follow them — a result cannot read "Ready"
    // while values are still waiting on a person.
    status: 'needs_review',
    reasons: [],
  } as Extraction
}

/**
 * A stand-in page image: an SVG laid out at the same coordinates as the boxes
 * above, so the evidence overlay lands on the right words in mock mode.
 */
export function pageSvg(): string {
  // SVG is XML, so a duplicated attribute is a fatal parse error rather than a
  // last-one-wins override. Size and weight are therefore parameters, not an
  // extra attribute string appended after a hard-coded font-size.
  const line = (x: number, y: number, text: string, size = 9, bold = false) =>
    `<text x="${x}" y="${y + 9}" font-family="monospace" font-size="${size}"` +
    `${bold ? ' font-weight="bold"' : ''}>${escapeXml(text)}</text>`

  const rows = LINE_ITEMS.map(
    (row) =>
      line(40, row.top, row.description) +
      line(300, row.top, row.quantity) +
      line(350, row.top, row.unit_price) +
      line(420, row.top, row.amount),
  ).join('')

  return `<svg xmlns="http://www.w3.org/2000/svg" width="595" height="842" viewBox="0 0 595 842">
<rect width="595" height="842" fill="#ffffff"/>
${line(40, 56, 'SOUTHERN STEEL TRADING SDN BHD', 12, true)}
${line(40, 69, 'Co. No. 201901234567   Tax ID C12345678901')}
${line(40, 82, '12 Jalan Perindustrian 3, 81100 Johor Bahru')}
${line(40, 108, 'TAX INVOICE', 11, true)}
${line(40, 121, 'Invoice No: INV-2026-0417')}
${line(330, 121, 'Date: 17/03/2026')}
${line(40, 134, 'PO Number: PO-88213')}
${line(330, 134, 'Payment Due: 16/04/2026')}
${line(40, 160, 'Bill To: Harapan Engineering Sdn Bhd')}
${line(40, 186, 'Description', 9, true)}
${line(300, 186, 'Qty', 9, true)}
${line(350, 186, 'Unit Price', 9, true)}
${line(420, 186, 'Amount', 9, true)}
<line x1="40" y1="195" x2="470" y2="195" stroke="#cbd5e1"/>
${rows}
<line x1="40" y1="245" x2="470" y2="245" stroke="#cbd5e1"/>
${line(40, 251, 'Subtotal')}${line(404, 251, 'RM1,984.00')}
${line(40, 264, 'SST 8%')}${line(414, 264, 'RM158.72')}
${line(40, 277, 'Total Due', 9, true)}${line(404, 277, 'RM2,142.72', 9, true)}
${line(40, 303, 'Terms: 30 days nett')}
</svg>`
}

function escapeXml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}

/**
 * The full invoice template.
 *
 * `GET /v1/templates` was captured with only three of its fields, so the schema
 * builder would offer three checkboxes. These are the real paths and labels from
 * `fdip/domain/templates.py`, with its descriptions shortened to one line each.
 */
const TEMPLATE_FIELDS: [string, string, string, boolean][] = [
  ['document_type', 'Document type', 'Invoice or credit note. A credit note reduces what is owed.', true],
  ['invoice_number', 'Invoice number', 'Labelled Invoice No, No. Invois or No. Nota Kredit.', true],
  ['invoice_date', 'Invoice date', 'Labelled Date or Tarikh. Malaysian documents write the day first.', true],
  ['due_date', 'Due date', 'Labelled Payment Due or Tarikh Bayaran.', false],
  ['po_number', 'PO number', "The buyer's purchase order reference.", false],
  ['do_number', 'DO number', 'The delivery order reference, labelled DO No.', false],
  ['vendor_name', 'Vendor name', 'The supplier issuing the document. Not the buyer.', true],
  ['vendor_registration_no', 'Vendor registration no', 'Labelled Co. No, ROC or No. Pendaftaran.', false],
  ['vendor_tax_id', 'Vendor tax ID', 'Labelled Tax ID, SST No or No. Cukai.', false],
  ['vendor_address', 'Vendor address', "The supplier's full address as printed.", false],
  ['vendor_contact', 'Vendor contact', "The supplier's telephone, fax or email.", false],
  ['buyer_name', 'Buyer name', 'Labelled Bill To, Sold To or Bil Kepada.', false],
  ['buyer_tax_id', 'Buyer tax ID', "The buyer's tax registration number if printed.", false],
  ['buyer_address', 'Buyer address', 'The billing address as printed.', false],
  ['currency', 'Currency', 'ISO 4217 code. RM and MYR both mean MYR.', true],
  ['subtotal', 'Subtotal', 'Total of the line items before tax. Labelled Jumlah Kecil.', true],
  ['discount_amount', 'Discount', 'Any discount deducted before tax. Omitted when not printed.', false],
  ['tax_rate', 'Tax rate', 'The percentage as a number, so 8 for 8 per cent.', false],
  ['tax_amount', 'Tax amount', 'The tax in currency, not the percentage.', false],
  ['tax_lines', 'Tax lines', 'One entry per rate when the document shows more than one.', false],
  ['rounding_adjustment', 'Rounding', 'Malaysian invoices round to the nearest 5 sen.', false],
  ['total', 'Total', 'The final amount payable. Labelled Jumlah Besar.', true],
  ['amount_in_words', 'Amount in words', 'The total written out, if printed.', false],
  ['payment_terms', 'Payment terms', 'For example 30 days nett or C.O.D.', false],
  ['bank_account', 'Bank account', "The supplier's account number for payment.", false],
  ['line_items', 'Line items', 'One entry per goods or service row in the table.', true],
  ['line_items[].description', 'Description', 'The whole cell verbatim, including any part code.', true],
  ['line_items[].quantity', 'Qty', 'Units ordered, labelled Qty or Kuantiti.', true],
  ['line_items[].unit_price', 'Unit price', 'Price for one unit, labelled Harga Seunit.', true],
  ['line_items[].amount', 'Amount', 'The row total, labelled Jumlah.', true],
  ['line_items[].tax_code', 'Tax code', 'Per-row tax code, if the table has that column.', false],
]

export function buildTemplate() {
  return [
    {
      id: 'tpl_invoice_v1',
      document_type: 'invoice',
      version: 1,
      name: 'Malaysian supplier invoice',
      description:
        'A Malaysian supplier invoice or credit note. Labels may be in English or Malay.',
      fields: TEMPLATE_FIELDS.map(([path, label, description, required]) => ({
        path,
        label,
        type: path.includes('amount') || path.includes('total') ? 'decimal' : 'string',
        description,
        required_default: required,
        is_array: path === 'line_items' || path === 'tax_lines',
      })),
    },
  ]
}

export function buildSchemaList() {
  return [
    {
      schema_id: 'sch_1m4an4fr241j5spk4',
      name: 'AP invoices',
      document_type: 'invoice',
      template_id: 'tpl_invoice_v1',
      current_version: 1,
      created_at: '2026-10-07T07:44:34',
      versions: [],
    },
  ]
}
