# FDIP API contract for the UI

Base URL `http://localhost:8000/v1`. Machine-readable: `openapi.json` in this folder,
also served at `/v1/openapi.json`, with Swagger at `/v1/docs`. Every example below was
**captured from a real mock-mode run**; the full set, including responses trimmed
here, is in `samples/examples.json`.

Three rules before anything else. **Branch on `code`, never on `detail`** — errors are
RFC 9457 problem details and `detail` is prose that will be reworded. **Decimals are
strings**: `"total": "2142.72"`, never `2142.72`, because a JSON number is a float on
your side and `12611.70` does not survive it. And **`processing` is the only
non-terminal status** — poll while it is `processing`, stop on anything else.

## Auth

Session cookie `fdip_session`, httpOnly, `SameSite=Lax`, set by login. Send
`credentials: "include"` on every request. CORS allows `http://localhost:5173` only;
change `FDIP_CORS_ORIGINS` to add an origin.

| Route | Body | Notes |
| --- | --- | --- |
| `POST /auth/register` | `{email, password}` | password ≥ 8 chars; creates a `Default` project; logs in |
| `POST /auth/login` | `{email, password}` | `401` with one message for any failure |
| `POST /auth/logout` | — | `204`; clears the cookie |
| `GET /auth/me` | — | `{"user": {"id", "email"}, "projects": [{"id", "name"}]}` |

Every UI route accepts `?project_id=`; it defaults to the first project. A project
id that is not yours returns **404**, not 403 — that is deliberate, and so is a
cross-project document returning 404. Dev login: `dev@fdip.local` / `devpass`.

## Upload and poll

`POST /documents`, multipart `file=<pdf|png|jpg|tiff>`, optional header
`Idempotency-Key` → `202` `{"document_id": "doc_1m4ab…", "job_id": "job_1m4ab…",
"status": "processing", "reused": false}`.

`reused: true` means those bytes were already in this project; no second extraction
is charged. Same `Idempotency-Key` with a **different** file is
`409 idempotency_conflict`. Then poll `GET /documents/{id}` **every 2 s** while
`status` is `processing`, and stop on any other value. There is no webhook.

```json
// GET /v1/documents/{id}  ->  200
{"id": "doc_1m4ab…", "filename": "invoice_digital.pdf", "mime": "application/pdf",
 "pages": 1, "page_sizes": {"1": [595.0, 842.0]}, "status": "completed",
 "error_code": null, "document_type": "invoice",
 "classification_confidence_source": {"confidence": 0.6, "source": "keyword"},
 "job": {"id": "job_1m4ab…", "state": "completed", "stage": "persist",
         "attempts": 1, "error_code": null},
 "decision": "completed", "created_at": "2026-10-07T04:49:51", "page_image_dpi": 150}
```

`GET /documents?status=&limit=&cursor=` lists them: `{items, next_cursor}`. Pass
`next_cursor` back as `cursor`; `null` means the end.

## Statuses

| Status | What the UI should do |
| --- | --- |
| `processing` | keep polling every 2 s |
| `completed` | show the data; it passed every check |
| `needs_review` | show the data **and** `reasons` plus per-field `reasons`; ask a human |
| `document_type_mismatch` | no data returned; tell the user the file is not that type |
| `rejected` | a reviewer rejected it; read-only |
| `failed` | processing error, `error_code` says why; offer a retry |
| `unsupported` | the file is refused and will never work; `error_code` says why |

## The extraction

`GET /documents/{id}/analysis` is the full-template run behind an interactive
upload; `GET /extractions/{id}` is the same shape. While the job is still running,
`analysis` returns `200` with `status: "processing"` and empty `data` — not a 404.

```json
{"extraction_id": "ext_1m4ab…", "document_id": "doc_1m4ab…", "version": 1,
 "status": "completed", "document_type": "invoice",
 "schema": {"id": "invoice", "version": 1}, "currency": "MYR",
 "data": {"invoice_number": "INV-2026-0417", "invoice_date": "2026-03-17",
          "subtotal": "1984.00", "tax_rate": "8", "tax_amount": "158.72",
          "total": "2142.72",
          "line_items": [{"description": "Hex bolt stainless M8 HBS-1000",
                          "quantity": "40", "unit_price": "12.50", "amount": "500.00"}]},
 "fields": {
   "invoice_number": {"value": "INV-2026-0417", "raw_text": "INV-2026-0417",
     "status": "accepted", "match": "exact", "reasons": [],
     "evidence": [{"page": 1, "bbox": [146.4, 118.7, 230.0, 127.7],
                   "source": "text_layer", "ocr_confidence": null}]},
   "line_items[0].amount": {"value": "500.00", "status": "accepted",
     "match": "exact", "evidence": [], "reasons": []}},
 "validation": [], "reasons": [], "pipeline_version": "2026.10.1",
 "created_at": "2026-10-07T04:49:51",
 "suggested_fields": ["currency", "invoice_date", "invoice_number", "..."]}
```

- `fields` is keyed by **path**. Line-item cells are `line_items[i].<column>`, `i`
  zero-based. That is the key to use when highlighting one cell.
- `match`: `exact` · `normalized` · `fuzzy_ocr` · `derived` · `not_found` ·
  `not_checked`. `exact`, `normalized` and `derived` are accepted; the rest go to
  review. `fuzzy_ocr` means "possible OCR misread" — show it differently.
- `derived` means the value is not printed but deterministic code confirmed it: an
  ISO currency code is rarely printed, and a total can be confirmed by arithmetic.
  Trustworthy, but say so in the UI.
- `status` per field: `accepted` · `needs_review` · `missing` · `corrected`.
- `validation[].severity` is `info` · `warning` · `critical`. Show criticals first;
  `subtotal_plus_tax_ne_total` is the one users care about.
- `suggested_fields` (analysis only) are the grounded paths — pre-tick these when
  the user turns a document into a schema.

## Boxes and page images

`GET /documents/{id}/pages/{n}/image` returns a **PNG at 150 DPI**, cacheable for a
day, with `X-Page-Dpi: 150`. `GET /documents/{id}/file` returns the original bytes.

- `bbox` is `[x0, y0, x1, y1]` in **PDF points**, origin **top-left**, y increasing
  **downwards** — the same direction as CSS.
- Scale by `image_width / page_width`, where `page_width` is `page_sizes["<n>"][0]`.
  At 150 DPI that is `150 / 72 ≈ 2.0833`.
- So `left = x0 * scale`, `top = y0 * scale`, `width = (x1 - x0) * scale`.

## Review

`POST /extractions/{id}/corrections` with
`{"changes": [{"path": "line_items[0].amount", "value": "505.00"}], "reason": "cell
misread"}` returns `201` and
`{"extraction_id": "ext_…new…", "version": 2, "status": "completed", …}`.

A correction **creates a new version** and re-runs validation and the decision;
the previous version is immutable and still readable. It costs no AI call. Use the
returned `extraction_id` from then on. `GET /documents/{id}/extractions` lists every
version.

`POST /extractions/{id}/decision` takes `{"action": "approve"}` or
`{"action": "reject", "reason": "duplicate"}` and returns
`{"extraction_id", "status"}`. `reject` requires a `reason`, and a rejected
extraction cannot be corrected (`409 already_decided`).

## Templates, schemas, keys

| Route | Purpose |
| --- | --- |
| `GET /templates` | the field catalogue: `{path, label, type, description, required_default, is_array}` |
| `POST /schemas` | `{template_id, name, fields:[path], locale_hints:{date_order}}` → `{schema_id, version}` |
| `GET /schemas` · `GET /schemas/{id}` | list, and detail with `versions[]` |
| `POST /schemas/{id}/versions` | a new **immutable** version |
| `GET /schemas/{id}/versions/{v}/contract` | the JSON Schema of the extraction response — give this to API customers |
| `POST /schemas/{id}/versions/{v}/test-runs` | `{document_ids:[3..5]}`; **required** before a key may use the version |
| `GET /test-runs/{id}` | `{status, per_document, passed}` |
| `POST /api-keys` | `{name, mode:"live"\|"test", schema_versions, expires_at?}` |
| `GET /api-keys` · `DELETE /api-keys/{id}` | list by prefix, revoke |
| `POST /exports` · `GET /exports/{id}` | `{format:"csv"\|"xlsx", document_ids?\|status?}`, then download |
| `GET /usage?month=YYYY-MM` | `{pages, documents, ai_cost_usd, by_key}` |
| `GET /jobs/{id}` · `GET /health` | job state; DB, worker heartbeat, provider mode (`/health` needs no auth) |

The `key` in the `POST /api-keys` response is shown **once** and is not retrievable:
warn the user before they close the dialog. Afterwards only `prefix` is available.
Test runs reuse the existing analysis, so they are free and repeatable, but every
document must already have been processed.

## Errors the UI must handle

```json
// 404
{"type": "https://fdip.local/problems/not_found", "title": "Not Found",
 "status": 404, "detail": "no such document", "code": "not_found",
 "instance": "/v1/documents/doc_does_not_exist"}
```

| `code` | HTTP | Meaning |
| --- | --- | --- |
| `unauthenticated` | 401 | no or bad session/key — send them to login |
| `forbidden` | 403 | authenticated but not allowed |
| `not_found` | 404 | wrong id, **or** another project's row |
| `idempotency_conflict` | 409 | same key, different file |
| `already_decided` | 409 | the extraction was rejected |
| `schema_test_run_required` | 409 | run a test run before using the version |
| `export_not_ready` | 409 | poll `GET /exports/{id}` |
| `file_too_large` | 413 | over 20 MB |
| `empty_file` · `corrupt_file` · `encrypted_pdf` · `unsupported_file_type` · `page_limit_exceeded` | 415 | the file is refused permanently; do not retry |
| `invalid_request` | 422 | bad field path, bad `date_order`, missing reason |
| `rate_limited` | 429 | 60/min per key; honour `Retry-After` |
| `quota_exceeded` | 429 | monthly page quota or AI ceiling reached |
| `provider_unavailable` · `internal` | 500 | retryable |

FastAPI's own validation failures come back as `422` with a `detail` **array** rather
than this shape; treat an array `detail` as a form error.

## Pipeline route (not for the UI)

`POST /extract` takes `Authorization: Bearer fdip_live_…`, not a cookie. The UI only
needs it to show customers a cURL example:

```bash
curl -X POST "http://localhost:8000/v1/extract?wait=30" \
  -H "Authorization: Bearer fdip_test_…" \
  -F "file=@invoice.pdf" -F "schema_id=sch_…" -F "schema_version=1"
```

`202` with `{document_id, job_id, status}`, or `200` with the full extraction if it
finished inside `wait` seconds. A `fdip_test_` key can never reach the live provider.
