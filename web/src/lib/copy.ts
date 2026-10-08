/**
 * Every user-facing word, in one place.
 *
 * Two rules from the master prompt govern this file.
 *
 * **"FDIP" never appears in the UI.** It is the internal name. The product is
 * **Marinnex Lab**.
 *
 * **No percentages.** The backend has no calibrated per-field confidence, so the
 * UI shows *verification states* — what was checked and how — never a number
 * nobody can audit. `VERIFICATION` below is the whole vocabulary; anything that
 * looks like an accuracy claim is a bug.
 *
 * Keeping the words here rather than inline means one term has one spelling
 * across the homepage, the workspace, the tour and the guide.
 */

export const BRAND = {
  name: 'Marinnex Lab',
  tagline: 'Turn financial documents into usable data.',
  /** C2: invoices only today. Nothing else may be claimed as supported. */
  supports: 'invoices',
} as const

export const HERO = {
  headline: 'Turn financial documents into usable data.',
  support:
    'Upload an invoice. Marinnex Lab reads it, shows you where every value came from, and hands back structured data your systems can use.',
  primaryCta: 'Process your first document',
  secondaryCta: 'See how it works',
} as const

/** The six steps of the product journey, used on Home, in the tour and the guide. */
export const JOURNEY = [
  { key: 'upload', title: 'Upload', body: 'Drop in a PDF or a photo of an invoice.' },
  { key: 'understand', title: 'Understand', body: 'We work out what the document is before reading it.' },
  { key: 'extract', title: 'Extract', body: 'Values are pulled out field by field.' },
  { key: 'review', title: 'Review', body: 'Every value points back at the words it came from.' },
  { key: 'select', title: 'Choose', body: 'Pick the fields you want back, and save them as a schema.' },
  { key: 'use', title: 'Use', body: 'Call the API from your own system and get the same data.' },
] as const

/**
 * C1 — verification states. One entry per backend match class.
 *
 * `label` is what a person reads. `meaning` is the one-line explanation behind
 * the "?" hint. Every state has an icon and text elsewhere in the UI, so colour
 * is never the only channel.
 */
export const VERIFICATION = {
  exact: {
    label: 'Found on page',
    meaning: 'This exact text appears on the document. Select it to see where.',
    tone: 'success',
  },
  normalized: {
    label: 'Found on page',
    meaning:
      'Found on the document after tidying formatting — a date written 17/03/2026, or an amount written RM1,984.00.',
    tone: 'success',
  },
  derived: {
    label: 'Calculated',
    meaning:
      'Not printed on the document, but worked out from values that are, and checked. A total confirmed by its subtotal and tax, for example.',
    tone: 'brand',
  },
  fuzzy_ocr: {
    label: 'Possible misread, please check',
    meaning:
      'Close to a word the scanner read with difficulty. The value may be right; it is worth a look.',
    tone: 'warning',
  },
  not_found: {
    label: 'Not found on page',
    meaning:
      'A value was produced but could not be located anywhere on the document. Treat it with suspicion.',
    tone: 'danger',
  },
  not_checked: {
    label: 'Not on document',
    meaning:
      'This document does not show this field. Absent, not zero — nothing is missing or wrong.',
    tone: 'neutral',
  },
} as const

export type VerificationKey = keyof typeof VERIFICATION

/**
 * Scan quality, shown **only** where the evidence came from OCR.
 *
 * It measures how clearly the scanner read the text, not whether the value is
 * correct. That distinction is in the tooltip, because conflating them is
 * exactly the accuracy claim C1 forbids.
 */
export const SCAN_QUALITY = {
  high: 'Scan quality: high',
  medium: 'Scan quality: medium',
  low: 'Scan quality: low',
  hint: 'How clearly the text was read from the scan. It does not say whether the value is right.',
} as const

export function scanQuality(confidence: number): keyof typeof SCAN_QUALITY {
  if (confidence >= 0.9) return 'high'
  if (confidence >= 0.75) return 'medium'
  return 'low'
}

/** Field status, as the API reports it. */
export const FIELD_STATUS = {
  accepted: 'Verified',
  needs_review: 'Needs review',
  missing: 'Not on document',
  corrected: 'You changed this',
} as const

/** Document status. Plain English, never the raw enum. */
export const DOC_STATUS = {
  processing: 'Reading…',
  completed: 'Ready',
  needs_review: 'Needs your review',
  document_type_mismatch: 'Not an invoice',
  rejected: 'Rejected',
  failed: "Couldn't process",
  unsupported: "Can't read this file",
} as const

/**
 * Staged loading messages, from `FIRST_TIME_USER_PROMPT.md`.
 *
 * These follow the real pipeline stages — probe, parse, classify, extract,
 * validate — but the API exposes only `job.stage`, so the UI advances through
 * them on a timer when the stage is unknown rather than pretending to know.
 */
export const PROCESSING_STEPS = [
  { stage: 'parse', text: 'Reading your document…' },
  { stage: 'classify', text: 'Working out what kind of document this is…' },
  { stage: 'extract', text: 'Finding financial information…' },
  { stage: 'decide', text: 'Checking extracted values…' },
  { stage: 'persist', text: 'Preparing your results…' },
] as const

export const GLOSSARY = {
  document: 'A file you uploaded — an invoice, as a PDF or a photo.',
  field: 'One piece of information on the document, like the invoice number.',
  needsReview:
    'Something about this document is worth a person checking before you rely on it.',
  verified: 'Every required field was found and every check passed.',
  schema:
    'A saved list of the fields you want back. Your systems ask for a schema by name and version, so the shape never changes under them.',
  apiKey:
    'A secure credential your application uses to connect to Marinnex Lab.',
  testKey: 'A key that never reaches the paid AI provider, so it costs nothing to use.',
  liveKey: 'A key that performs real extractions, and is billed.',
  structuredData:
    'Information taken out of your document in a format software can use.',
  evidence:
    'The place on the page a value was found, so you can check it yourself.',
} as const

/** C5 — trust. Only facts that are true of this system today. */
export const TRUST_FACTS = [
  {
    title: 'Where your documents are processed',
    body: 'AI processing is performed by DeepSeek, whose servers are in China. Your document text is sent there to be read.',
  },
  {
    title: 'Where your documents are stored',
    body: 'Files and extracted data are stored on the machine running Marinnex Lab. Malaysian hosting is planned and is not live yet.',
  },
  {
    title: 'Every value can be checked',
    body: 'Each field records the page and the position it came from. Anything that could not be located is flagged rather than quietly accepted.',
  },
  {
    title: 'A person decides',
    body: 'Scanned documents are always reviewed by a person before acceptance. Nothing is auto-approved on a scan.',
  },
  {
    title: 'Your API keys',
    body: 'Only a hash of each key is stored, so a key cannot be recovered — only replaced. The key itself is shown once, when it is created.',
  },
] as const

/** C9 — errors stay friendly, but keep the code reachable for developers. */
export const ERROR_COPY = {
  genericTitle: "We couldn't process this document.",
  genericBody: 'The file may be unclear, damaged, or a type we cannot read yet.',
  detailsLabel: 'Technical details',
  retry: 'Try again',
  uploadAnother: 'Upload another document',
  formats: 'See supported files',
} as const

export const SUPPORT_URL: string | undefined =
  import.meta.env.VITE_SUPPORT_URL || undefined
