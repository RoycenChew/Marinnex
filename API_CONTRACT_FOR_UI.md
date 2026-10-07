# FDIP API contract for the UI

Base URL `http://localhost:8000/v1`. Machine-readable: `openapi.json` here, also served
at `/v1/openapi.json`, with Swagger at `/v1/docs`.

**Two ways to develop against this.** Run the backend per `README_RUN.md` (mock
provider mode: no spend, no API key), or work offline from `samples/examples.json`
behind `VITE_USE_MOCKS=true` — 21 responses keyed by `"<METHOD> /v1/<path>"` as
`{status, body}`, every one **captured from a real run** rather than typed, including a
scan and an error; a few long bodies are trimmed and say so in `_fields_note`. Use the
real backend before shipping, since mocks cannot catch a polling or CORS mistake.

Three rules first. **Branch on `code`, never on `detail`** — errors are RFC 9457
problem details and `detail` is prose that will be reworded. **Decimals are strings**:
`"total": "2142.72"`, never `2142.72`, because a JSON number is a float on your side.
And **`processing` is the only non-terminal status** — poll while it is `processing`.

## Auth

Session cookie `fdip_session`, httpOnly, `SameSite=Lax`, set by login. Send
`credentials: "include"` on every request. CORS allows only the origins in
`FDIP_CORS_ORIGINS` (default `http://localhost:5173`).

| Route | Body | Notes |
| --- | --- | --- |
| `POST /auth/register` | `{email, password}` | password ≥ 8 chars; creates a `Default` project; logs in |
| `POST /auth/login` | `{email, password}` | `401` with one message for any failure |
| `POST /auth/logout` | — | `204`; clears the cookie |
| `GET /auth/me` | — | `{"user": {"id", "email"}, "projects": [{"id", "name"}]}` |

Every UI route accepts `?project_id=`, defaulting to the first. A project id that is not
yours returns **404**, not 403 — deliberate, as is a cross-project document. Dev login:
`dev@fdip.local` / `devpass`.

## Upload and poll

`POST /documents`, multipart `file=<pdf|png|jpg|tiff>`, optional header `Idempotency-Key`
→ `202` `{"document_id", "job_id", "status": "processing", "reused": false}`.

`reused: true` means those bytes were already in this project, so no second extraction
is charged; the same `Idempotency-Key` with a **different** file is
`409 idempotency_conflict`. Then poll `GET /documents/{id}` **every 2 s** while `status`
is `processing`, stopping on any other value — there is no webhook.

`GET /documents/{id}` returns `{id, filename, mime, pages, page_sizes, status,
error_code, document_type, decision, classification_confidence_source, job:{id, state,
stage, attempts, error_code}, created_at, page_image_dpi}`. `GET /documents?status=&
limit=&cursor=` lists them as `{items, next_cursor}`; pass `next_cursor` back as
`cursor`, and `null` means the end. Full examples in `samples/examples.json`.

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

`GET /documents/{id}/analysis` is the full-template run behind an interactive upload,
and `GET /extractions/{id}` is the same shape. While the job runs it returns `200`
with `status: "processing"` and empty `data` — not a 404.

```json
{"extraction_id": "ext_1m4ab…", "document_id": "doc_1m4ab…", "version": 1,
 "status": "completed", "document_type": "invoice", "schema": {"id": "invoice", "version": 1},
 "currency": "MYR", "data": {"invoice_number": "INV-2026-0417", "total": "2142.72",
   "line_items": [{"description": "Hex bolt M8 HBS-1000", "amount": "500.00"}]},
 "fields": {
   "invoice_number": {"value": "INV-2026-0417", "raw_text": "INV-2026-0417",
     "status": "accepted", "match": "exact", "reasons": [],
     "evidence": [{"page": 1, "bbox": [146.4, 118.7, 230.0, 127.7],
                   "source": "text_layer", "ocr_confidence": null}]},
   "line_items[0].amount": {"value": "500.00", "status": "accepted",
     "match": "exact", "evidence": [], "reasons": []}},
 "validation": [], "reasons": [], "pipeline_version": "2026.10.1",
 "suggested_fields": ["currency", "invoice_date", "..."], "created_at": "2026-10-07T04:49:51"}
```

- `fields` is keyed by **path**; line-item cells are `line_items[i].<column>`, `i`
  zero-based. That is the key to use when highlighting one cell.
- `match`: `exact` · `normalized` · `fuzzy_ocr` · `derived` · `not_found` ·
  `not_checked`. The first two and `derived` are accepted; the rest go to review, and
  `fuzzy_ocr` means "possible OCR misread" — show it differently.
- `derived`: not printed, but deterministic code confirmed it from evidence on the page
  — a currency by its `RM`/`MYR`/`S$` marker, a total by arithmetic, a tax amount by its
  rate. Those three fields only. Trustworthy, but worth saying so in the UI.
- `status` per field: `accepted` · `needs_review` · `missing` · `corrected`.
- `validation[].severity` is `info` · `warning` · `critical`; show criticals first, and
  `subtotal_plus_tax_ne_total` is the one users care about.
- `suggested_fields` (analysis only) are the grounded paths — pre-tick these when the
  user turns a document into a schema.

### Two renderings the UI must get right

**A scan always returns `needs_review`** with `scanned_document_review` among its
`reasons`, however clean the page is — it is unconditional, not a judgement about that
file, because route B measured 13 silent errors in 30 mild scans. Show an **info
banner, not an error**, and expect other `reasons` beside it:

> Scanned documents are reviewed by a person before acceptance.

**A field with nothing printed comes back absent, never zero**: `value: null`,
`status: "missing"`, `match: "not_checked"`, no evidence. Render those as
**"Not on document"** — not `0`, not an empty box, not an error, because nothing is
wrong. Twelve template fields are usually in this state; only `needs_review` wants
attention. `field_not_grounded:<path>` is the opposite case — a value was returned that
is *not* on the page — so highlight it and show no box, because there is none. It
applies to **optional** fields too: an optional field tolerates being absent, not being
wrong, while a null optional field completes.

## Boxes and page images

`GET /documents/{id}/pages/{n}/image` returns a **PNG at 150 DPI**, cacheable for a day,
with `X-Page-Dpi: 150`; `GET /documents/{id}/file` returns the original bytes.

- `bbox` is `[x0, y0, x1, y1]` in **PDF points**, origin **top-left**, y **down** — the
  same direction as CSS.
- Scale by `image_width / page_width` (`page_sizes["<n>"][0]`), which at 150 DPI is
  `150 / 72 ≈ 2.0833`: `left = x0 * scale`, `width = (x1 - x0) * scale`.

## Review

`POST /extractions/{id}/corrections` with `{"changes": [{"path":
"line_items[0].amount", "value": "505.00"}], "reason": "cell misread"}` returns `201`
and `{"extraction_id": "ext_…new…", "version": 2, "status": "completed", …}`.

A correction **creates a new version** and re-runs validation and the decision; the
previous version is immutable and still readable, and it costs no AI call. Use the
returned `extraction_id` from then on; `GET /documents/{id}/extractions` lists all.

`POST /extractions/{id}/decision` takes `{"action": "approve"}` or `{"action":
"reject", "reason": "duplicate"}` and returns `{"extraction_id", "status"}`. `reject`
requires a `reason`, and a rejected extraction cannot be corrected
(`409 already_decided`).

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
warn the user before they close the dialog; afterwards only `prefix` is available.
Test runs reuse the existing analysis, so they are free and repeatable, but each
document must already have been processed.

## Errors the UI must handle

Shape `{type, title, status, detail, code, instance}`, e.g. `{"status": 404, "code":
"not_found", "detail": "no such document", "instance": "/v1/documents/doc_x"}`.

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
| `empty_file` · `corrupt_file` · `encrypted_pdf` · `unsupported_file_type` · `page_limit_exceeded` | 415 | refused permanently; do not retry |
| `invalid_request` | 422 | bad field path, bad `date_order`, missing reason |
| `rate_limited` | 429 | 60/min per key; honour `Retry-After` |
| `quota_exceeded` | 429 | monthly page quota or AI ceiling reached |
| `provider_unavailable` · `internal` | 500 | retryable |

FastAPI's own validation failures come back as `422` with a `detail` **array**, not this shape: treat an array `detail` as a form error.

## Pipeline route (not for the UI)

`POST /extract` takes `Authorization: Bearer fdip_live_…`, not a cookie. The UI needs it
only to show customers a cURL example:

```bash
curl -X POST "http://localhost:8000/v1/extract?wait=30" \
  -H "Authorization: Bearer fdip_test_…" \
  -F "file=@invoice.pdf" -F "schema_id=sch_…" -F "schema_version=1"
```

`202` with `{document_id, job_id, status}`, or `200` with the full extraction if it
finished inside `wait`. A `fdip_test_` key can never reach the live provider.
