# Backend requests

Gaps found while building the UI. Four are now fixed in the backend; the rest are
open, each worked around in the front end with the workaround marked in code.

## Fixed

### 1. `?project_id=` is now declared in `openapi.json` ✅

It was read off the raw request inside a FastAPI dependency, so it never reached
the schema and the generated client refused it. `session_principal` now takes it
as a declared `Query` parameter, which puts it on **27 operations** at once.

`src/api/queries.ts` no longer casts anything.

### 2. Every route now has a `response_model` ✅

The handlers were annotated `-> dict[str, Any]`, so each 200 body generated as
`{[key: string]: unknown}`. `fdip/api/schemas.py` holds the models, transcribed
from `fdip/api/views.py`, which already built every response dict in one place.

**16 of 20** JSON responses are now typed. The four that are not are correctly
untyped: `/documents/{id}/file` and `/pages/{n}/image` return bytes,
`/exports/{id}` returns a spreadsheet, and
`/schemas/{id}/versions/{v}/contract` *is* a free-form JSON Schema by definition.

`src/api/types.ts` is now a set of aliases over the generated schemas rather than
hand-written shapes. Run `npm run gen:api` after any backend change.

### 3. API keys have a `status` field ✅

`active | expired | revoked`, derived once in `views.api_key_status` instead of in
every client. The UI no longer computes it.

### 4. `document_type` is derived, and the type gate applies everywhere ✅

Not strictly from this list, but it came from the same UI session. `document_type`
was grounded against page text and no invoice prints the word "invoice" as a value
— the Malay sample says INVOIS CUKAI — so it returned `not_found` and held the
document back over a field the classifier already knew. It now takes the
classifier's answer with match `derived`.

The type gate used to apply only to pipeline calls, so a bank statement uploaded
interactively reached `completed` under the invoice template. It now applies on
every route: the pipeline still refuses outright, and an interactive upload is
extracted but carries `document_type_mismatch` as a reason on a `needs_review`.

---

## Still open

### 5. No document search endpoint

`GET /v1/documents` filters by `status` and paginates by cursor, but there is no
query by filename, vendor, invoice number or date range.

**Workaround:** the ⌘K palette navigates between screens only. A palette that
silently fails to find a document the user knows exists is worse than one that
does not claim to search.

**Ask:** `GET /v1/documents?q=` over filename and, ideally, extracted
`invoice_number` and `vendor_name`.

**Why not fixed:** this is a new feature with a schema-design question behind it
(which fields are searchable, and whether it needs an index), not a one-line
annotation.

### 6. No aggregate document counts

`GET /v1/usage` gives pages, documents and AI cost for the month. Nothing gives
counts by status, so the Documents KPI row can only count the page in view.

**Workaround:** those two cards are labelled "In the list below" and "of N
decided" rather than implying a month-wide figure.

**Ask:** `GET /v1/documents/stats?month=` returning counts by status.

**Why not fixed:** same reason — a new endpoint, and one whose caching behaviour
wants thinking about before it is added.

### 7. No way to poll an export

Exports are built synchronously today, so `POST /v1/exports` returning
`{export_id, status, row_count}` is final and the UI treats it as such. But the
contract describes a poll-then-download flow and there is no status-only
endpoint: the only way to ask "is it ready" is to request the file and handle a
409.

**Ask:** either document that exports are synchronous, or add
`GET /v1/exports/{id}/status` before they become asynchronous.

**Why not fixed:** nothing is broken yet. It becomes real the day exports move to
the worker.

### 8. `GET /v1/documents/{id}/extractions` returns a bare array

Inconsistent with `GET /v1/documents`, which returns `{items, next_cursor}`. A
document with many correction versions will eventually want paging, and changing
the shape later is a breaking change.

**Why not fixed:** changing it now would break the UI that was just built against
it, for a problem that does not exist yet. Worth doing before the first external
consumer, not after.

### 9. Page images cannot be loaded from an `<img src>` cross-origin

Not a backend defect — `<img>` does not send credentials cross-origin, and in
development the UI is on `:5173` while the API is on `:8000`.

**Workaround:** the review screen fetches the image with
`credentials: "include"` and renders it from an object URL. Noted only because it
looks like a backend problem when the image 401s.
