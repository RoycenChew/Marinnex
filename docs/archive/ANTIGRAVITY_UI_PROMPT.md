# UI build prompt: FDIP web app

**For the UI coding agent.** Build the web front end for an existing, running backend.

**The backend is the source of truth.** Read these before writing code:

- `fdip/openapi.json`
- `fdip/API_CONTRACT_FOR_UI.md`
- `fdip/README_RUN.md`

If anything below disagrees with those files, the files win.

**Rules:**
- Do not change any backend code.
- Do not invent endpoints.
- If something you need is missing from the API, list it in `web/BACKEND_REQUESTS.md`
  and work around it with a clearly marked stub.

---

## 1. What the product is

FDIP (Financial Document Intelligent Processing) turns financial documents (invoices
first) into structured, evidence-backed JSON.

A user:
1. uploads a document
2. sees what the system extracted, with every value highlighted on the page where it
   was found
3. picks the fields they want
4. confirms a schema and tests it on a few samples
5. creates an API key, so their own system can send documents and get the same JSON
   back

**The UI must stay thin.** All validation, decisions and calculations happen in the
backend. The UI displays them and sends user actions; it never recomputes totals,
statuses or confidence.

**Audience:** finance staff and developers in Malaysia. The UI is in English. Amounts
are shown as received from the API, e.g. `MYR 12,611.70`. Dates are shown as
`DD/MM/YYYY`; the API's ISO date stays visible in tooltips.

---

## 2. Stack and setup

- **Framework:** Vite, React 18 and TypeScript, in folder `fdip/web/`.
- **Data and routing:**
  - TanStack Query for server state
  - React Router
  - types generated from `openapi.json` with `openapi-typescript`, plus a thin `fetch`
    wrapper
- **Styling:** Tailwind CSS. Clean, dense and professional; light and dark themes.
- **Endpoints:**
  - dev server: `http://localhost:5173`
  - API: `http://localhost:8000/v1`, configurable via `VITE_API_BASE`
  - every request uses `credentials: "include"` (session cookie)
- **No PDF library needed.** Page images come from
  `GET /documents/{id}/pages/{n}/image`.
- **Mock mode:** `VITE_USE_MOCKS=true` uses MSW with the example responses in
  `API_CONTRACT_FOR_UI.md`, so the UI runs without the backend.

---

## 3. Screens (MVP)

### 1. Login and register

- `POST /auth/login` and `POST /auth/register`; `GET /auth/me` on load.
- Show a project switcher if the user has more than one project.
- The dev account `dev@fdip.local` / `devpass` exists when the backend is seeded.

### 2. Documents (home)

- **Upload area:** drag and drop, PDF/PNG/JPG, with a progress bar →
  `POST /documents`.
- **Table:** filename, type, status badge, decision, created time; filter by status.
- **Polling:** while any row is `processing`, poll every 2 s and stop when none are.
- **Status badge colours:**
  - completed: green
  - needs_review: amber
  - processing: blue, animated
  - document_type_mismatch, unsupported, failed: red/grey, with the error code in a
    tooltip
  - rejected: grey

### 3. Document analysis and review: the core screen

**Layout:** a page viewer on the left, the extracted fields on the right.

**Page viewer:**
- page images with page tabs or thumbnails
- zoom (fit width / 100% / 150%)

**Highlights:**
- Draw each field's `evidence` boxes over the image.
- Scale = rendered image width / `page_sizes[page][0]`; boxes are top-left origin,
  y-down.
- Selecting a field scrolls to and highlights its box; clicking a box selects its field.

**Field list, grouped as** Header, Totals, Line items:
- Each field shows its value, a match badge and its status (accepted / needs review),
  with `reasons` as readable text.
- Match badges: `exact`, `normalized`, `fuzzy_ocr` ("possible OCR misread"),
  `not_found` ("not found on page"), `derived`.
- Line items render as an editable table; each cell highlights its own box.

**Corrections:**
- Inline editing. Saving sends `POST /extractions/{id}/corrections` with all changes
  together, then refreshes to the new version.
- Show the version number and a version history dropdown.

**Actions:**
- Approve or reject (reject needs a reason) → `POST /extractions/{id}/decision`.
- Never let the user approve while a save is pending.

**Also:**
- a banner when the status is `needs_review` explaining why
- a banner for `document_type_mismatch`

### 4. Field selection → schema

- From the analysis screen: "Create API schema from this document".
- Load `GET /templates`. Show every template field with a checkbox; pre-tick
  `suggested_fields` from the analysis, and label them "found in this document".
- Inputs: schema name, date order (DMY default).
- Create with `POST /schemas`; new versions with `POST /schemas/{id}/versions`.

### 5. Schema detail

- List versions.
- Show the contract JSON (`GET …/contract`) with a copy button.
- **Test run:**
  - pick 3–5 uploaded documents → `POST …/test-runs`
  - poll `GET /test-runs/{id}`
  - show per-document results and an overall pass/fail
- A key can only be created for a version whose test run passed. Disable the button
  otherwise, with an explanation.

### 6. API keys

- Create: name, mode (live/test), schema versions, optional expiry.
  - Show the full key **once**, in a modal with a copy button and a warning that it will
    not be shown again.
- List keys by prefix, mode, schemas, created, last used and status; revoke with a
  confirmation.
- **Developer panel** for a selected schema version:
  - generated cURL and Python examples for `POST /v1/extract` (with `?wait=30`)
  - an example response built from the contract
  - a "test it here" form that uploads a file using a test key and shows the JSON
    response

### 7. Exports and usage

- **Exports:** choose CSV or XLSX and a filter (status, or selected documents) →
  `POST /exports`, then poll and download.
- **Usage:** a month picker; pages, documents and AI cost, plus a small per-key table.

---

## 4. Behaviour rules

- Show RFC 9457 errors (`title`, `detail`, `code`) in a toast. Map common codes to
  friendly text:
  - `unsupported_file_type`
  - `encrypted_pdf`
  - `page_limit_exceeded`
  - `quota_exceeded`
  - `schema_version_not_allowed`
- `401` → redirect to login. `404` on a document → a "not found or no access" page.
- **Never log or store** extracted values or keys in `localStorage`. Session state lives
  in the cookie only.
- **Accessibility:** keyboard navigation through fields, visible focus, and highlight
  colours that keep text readable in both themes.
- **Empty and loading states** for every list. Skeletons, not spinners, on the analysis
  screen.

---

## 5. Done when

1. `npm run dev` with the backend running works end to end:
   - log in as the dev user
   - upload `fdip/samples/invoice_digital.pdf`
   - watch it process
   - review it, with highlights on the correct words
   - correct a field, which creates a new version
   - approve it
   - create a schema
   - pass a test run
   - create a test key
   - call extract from the developer panel
   - export XLSX
2. The scanned sample shows OCR evidence boxes in the right places. The non-invoice
   sample shows the mismatch or unsupported state.
3. `npm run build` passes, with no TypeScript errors.
4. `VITE_USE_MOCKS=true npm run dev` works without the backend.
5. A short `web/README.md` covers how to run it, environment variables, regenerating
   types (`npm run gen:api`), and anything listed in `BACKEND_REQUESTS.md`.
