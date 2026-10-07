/**
 * Response shapes the generated types do not carry.
 *
 * **Why these are hand-written.** Most FDIP route handlers are annotated
 * `-> dict[str, Any]` rather than with a Pydantic `response_model`, so
 * `openapi.json` describes their 200 body as `{[key: string]: unknown}`. The
 * generated `v1.d.ts` is therefore correct but useless for these endpoints.
 *
 * The shapes below are transcribed from `API_CONTRACT_FOR_UI.md` and verified
 * against `samples/examples.json`, which is captured from a real run. They are a
 * **stub for a backend gap**, logged in `web/BACKEND_REQUESTS.md`: when the
 * handlers gain response models, regenerate with `npm run gen:api` and delete
 * this file.
 *
 * Nothing here is invented. Every field appears in a captured response.
 */

export type DocumentStatus =
  | 'processing'
  | 'completed'
  | 'needs_review'
  | 'document_type_mismatch'
  | 'rejected'
  | 'failed'
  | 'unsupported'

export type Evidence = {
  page: number
  bbox: [number, number, number, number] | null
  source: 'text_layer' | 'ocr' | 'vision'
  ocr_confidence: number | null
}

export type FieldEntry = {
  value: unknown
  raw_text: string | null
  status: 'accepted' | 'needs_review' | 'missing' | 'corrected'
  match: 'exact' | 'normalized' | 'fuzzy_ocr' | 'derived' | 'not_found' | 'not_checked'
  evidence: Evidence[]
  reasons: string[]
}

export type ValidationResult = {
  code: string
  severity: 'info' | 'warning' | 'critical'
  path: string | null
  message: string
}

export type LineItem = Record<string, string | null>

export type ExtractionData = {
  invoice_number?: string | null
  invoice_date?: string | null
  due_date?: string | null
  po_number?: string | null
  vendor_name?: string | null
  vendor_tax_id?: string | null
  buyer_name?: string | null
  currency?: string | null
  subtotal?: string | null
  tax_rate?: string | null
  tax_amount?: string | null
  total?: string | null
  line_items?: LineItem[] | null
  [key: string]: unknown
}

export type Extraction = {
  extraction_id: string
  document_id: string
  version: number
  status: DocumentStatus
  document_type: string | null
  schema: { id: string; version: number }
  currency: string | null
  data: ExtractionData
  fields: Record<string, FieldEntry>
  validation: ValidationResult[]
  reasons: string[]
  pipeline_version: string
  created_at: string | null
  /** Analysis responses only. */
  suggested_fields?: string[]
  /** Present while the job is still running, when `fields` is empty. */
  job?: JobView | null
  detail?: string
}

export type JobView = {
  id: string
  document_id?: string
  state: string
  stage: string | null
  attempts: number
  error_code: string | null
  created_at?: string | null
  finished_at?: string | null
}

export type DocumentDetail = {
  id: string
  filename: string
  mime: string
  pages: number
  page_sizes: Record<string, [number, number]>
  status: DocumentStatus
  error_code: string | null
  document_type: string | null
  classification_confidence_source: {
    confidence: number | null
    source: string
  } | null
  job: JobView | null
  decision: string | null
  created_at: string | null
  page_image_dpi: number
}

export type DocumentListItem = {
  id: string
  filename: string
  status: DocumentStatus
  document_type: string | null
  pages: number
  created_at: string | null
  decision: string | null
}

export type DocumentList = {
  items: DocumentListItem[]
  next_cursor: string | null
}

export type TemplateField = {
  path: string
  label: string
  type: string
  description: string
  required_default: boolean
  is_array: boolean
  enum?: string[]
  money?: boolean
  grounding?: string
}

export type Template = {
  id: string
  document_type: string
  version: number
  name: string
  description: string
  fields: TemplateField[]
}

export type SchemaVersion = {
  version: number
  created_at: string | null
  test_run_status: 'none' | 'passed' | 'failed' | string
  fields: string[]
  locale_hints: Record<string, string>
}

export type SchemaSummary = {
  schema_id: string
  name: string
  document_type: string
  template_id: string
  current_version: number
  created_at: string | null
  versions: SchemaVersion[]
}

export type TestRun = {
  test_run_id: string
  schema_id: string
  version: number
  status: string
  passed: boolean
  per_document: {
    document_id: string
    status: string
    fields_ok: number
    fields_total: number
  }[]
  created_at: string | null
  finished_at: string | null
}

export type ApiKey = {
  id: string
  name: string
  prefix: string
  mode: 'live' | 'test'
  schema_versions: { schema_id: string; version: number }[]
  expires_at: string | null
  revoked_at: string | null
  last_used_at: string | null
  created_at: string | null
}

/** Only the create response carries `key`, and only once. */
export type CreatedApiKey = {
  id: string
  prefix: string
  mode: 'live' | 'test'
  key: string
  detail: string
}

export type Usage = {
  month: string
  pages: number
  documents: number
  ai_cost_usd: number
  by_key: {
    api_key_id: string | null
    pages: number
    documents: number
    ai_cost_usd: number
  }[]
}

export type ExportJob = {
  export_id: string
  format: 'csv' | 'xlsx'
  status: string
  row_count: number
  error_code?: string | null
  created_at?: string | null
  finished_at?: string | null
}

export type Health = {
  status: string
  database: string
  provider_mode: string
  model: string
  extract_thinking: string
  worker_last_lease: string | null
  pipeline_version: string
}
