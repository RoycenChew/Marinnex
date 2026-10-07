# Backend requests

Gaps found while building the UI. Each one is worked around in the front end, and
the workaround is marked in code. Nothing here blocks the UI; all of it would make
the UI smaller and better typed.

Ordered by how much they cost.

---

## 1. `?project_id=` is accepted but undeclared in `openapi.json`

**Where:** every session-authenticated route.

`API_CONTRACT_FOR_UI.md` says "Every UI route accepts `?project_id=`, defaulting to
the first", and the backend does honour it — `session_principal` reads it with
`request.query_params.get("project_id")`. Because it is pulled off the raw request
inside a dependency rather than declared as a FastAPI `Query` parameter, it never
reaches the OpenAPI document. The generated client therefore types these routes as
`query?: never` and refuses the parameter.

**Workaround:** `src/api/queries.ts` casts the query object. That cast is the only
reason that file exists.

**Ask:** declare `project_id: str | None = Query(None)` on the routes, or make
`session_principal` a proper dependency with a declared parameter.

---

## 2. Responses have no `response_model`, so every body is `{[key: string]: unknown}`

**Where:** documents, analysis, extractions, schemas, test runs, API keys, usage,
exports — nearly everything.

The handlers are annotated `-> dict[str, Any]`, so `openapi.json` describes their
200 bodies as free-form objects. `openapi-typescript` faithfully generates
`{[key: string]: unknown}`, which gives the UI no type safety at all on the data it
exists to display.

**Workaround:** `src/api/types.ts` hand-writes the shapes, transcribed from
`API_CONTRACT_FOR_UI.md` and checked against `samples/examples.json`. It is a stub,
and it will drift.

**Ask:** add Pydantic response models. `fdip/api/views.py` already builds these
dicts in one place, so the models are mostly a transcription of what it returns.
When they exist, run `npm run gen:api` and delete `src/api/types.ts`.

---

## 3. No document search endpoint

**Where:** `GET /v1/documents` filters by `status` and paginates by cursor, but
there is no query by filename, vendor, invoice number or date range.

**Workaround:** the ⌘K palette navigates between screens only. It deliberately does
not offer document search, because a palette that silently fails to find a document
the user knows exists is worse than one that does not claim to.

**Ask:** `GET /v1/documents?q=` over filename and, ideally, extracted
`invoice_number` and `vendor_name`.

---

## 4. No aggregate document counts

**Where:** the Documents KPI row.

`GET /v1/usage` gives pages, documents and AI cost for the month. There is nothing
that gives counts by status, so "needs review" and the auto-accept rate can only be
computed from the page of documents currently loaded.

**Workaround:** those two cards are labelled "In the list below" and "of N decided"
rather than implying a month-wide figure.

**Ask:** `GET /v1/documents/stats?month=` returning counts by status, so the KPI row
reflects the project rather than the current page.

---

## 5. API keys have no `status` field

**Where:** `GET /v1/api-keys`.

The response carries `expires_at`, `revoked_at` and `last_used_at`, but not a single
derived state. Every client has to re-implement the same three-way comparison, and
they will not all agree on what "expired at exactly now" means.

**Workaround:** the UI derives `active | expired | revoked` from the timestamps.

**Ask:** add `status: "active" | "expired" | "revoked"`.

---

## 6. No way to poll an export, and no declared download type

**Where:** `POST /v1/exports` returns `{export_id, status, row_count}` and
`GET /v1/exports/{id}` returns the file bytes or `409 export_not_ready`.

Exports are built synchronously today, so this works. But the contract describes a
poll-then-download flow, and there is no status-only endpoint: the only way to ask
"is it ready" is to request the file and handle a 409.

**Workaround:** the UI treats the create response as final, since it is.

**Ask:** either document that exports are synchronous, or add
`GET /v1/exports/{id}/status`.

---

## 7. `GET /v1/documents/{id}/extractions` returns a bare array

Not a bug, but inconsistent with `GET /v1/documents`, which returns
`{items, next_cursor}`. A document with many correction versions will eventually
want paging, and changing the shape later is a breaking change.

---

## 8. Page images cannot be fetched with the session cookie from an `<img>` tag

**Where:** `GET /v1/documents/{id}/pages/{n}/image`.

`<img src>` does not send credentials cross-origin. In development the UI runs on
`:5173` and the API on `:8000`, so the review screen's page images are a
cross-origin request without the session cookie.

**Workaround:** the UI fetches the image with `credentials: "include"` and renders
it from an object URL.

**Ask:** nothing required — this is a browser rule, not a backend defect. Noted
because it looks like a backend problem when the image 401s.
