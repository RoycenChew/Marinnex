# FDIP web

The front end for the FDIP backend in the folder above. Vite, React 19,
TypeScript, Tailwind v4, TanStack Query, Radix.

## Run it

Two ways. Mock mode needs nothing else running.

```powershell
npm install
npm run dev            # http://localhost:5173
```

`.env.development` sets `VITE_USE_MOCKS=true`, so a plain `npm run dev` serves
the whole app from MSW with no backend and no spend.

Against the real backend, start it first (see `../README_RUN.md`), then:

```powershell
$env:VITE_USE_MOCKS = "false"
npm run dev
```

Sign in with `dev@fdip.local` / `devpass`, which exists when the backend is
seeded.

## Scripts

| Command | What it does |
| --- | --- |
| `npm run dev` | dev server on 5173 |
| `npm run build` | typecheck (`tsc -b`) then build. Must pass with no errors |
| `npm run preview` | serve the built output |
| `npm run lint` | oxlint |
| `npm run gen:api` | regenerate `src/api/v1.d.ts` from `../openapi.json` |

## Environment

| Variable | Default | Notes |
| --- | --- | --- |
| `VITE_USE_MOCKS` | `true` in development | `true` serves everything from MSW |
| `VITE_API_BASE` | `http://localhost:8000` | **Origin only.** The generated paths already start with `/v1` |

`.env.development` must be **UTF-8 without a BOM**. It was UTF-16 once, and Vite
silently served an env object with no `VITE_USE_MOCKS` key at all — mock mode
appeared to be on and was not.

## How it is put together

```
src/
  api/        client.ts, generated v1.d.ts, hand-written types.ts, queries.ts
  components/ ui/ primitives, layout/ shell, review/ page viewer + field panel
  lib/        tokens helpers: utils, format, status vocabularies, theme
  mocks/      MSW handlers and the fixtures that fill gaps in the captured data
  pages/      one file per screen
```

**Tokens live in `src/index.css`.** Tailwind v4 is CSS-first, so that file is the
config — there is no `tailwind.config.js`. Components reference semantic tokens
(`--surface-raised`, `--text-secondary`, `--accent-solid`), never a slate number,
which is why dark mode is a short override rather than a second set of classes. A
one-off hex anywhere else is a bug.

**`src/api/types.ts` and `queries.ts` are a workaround**, not the design. The
backend's handlers return bare dicts, so every response generates as
`{[key: string]: unknown}`, and `?project_id=` is accepted but undeclared. Those
two files hold every cast so the screens above them are honestly typed. See
`BACKEND_REQUESTS.md`; when the backend gains response models, run
`npm run gen:api` and delete `types.ts`.

**Mock fixtures.** `src/mocks/fixtures.ts` fills three gaps in
`../samples/examples.json`: the analysis and template responses were trimmed when
they were captured, and the page image is binary so it was never captured at all.
Without it, mock mode shows a review screen with three fields and no page.

## Conventions

- **Money is never parsed.** The API sends decimals as strings because a JSON
  number is a float on this side; `formatMoney` formats the string and the UI does
  no arithmetic at all.
- **Dates render `DD/MM/YYYY`** with the ISO value in a `title`.
- **Nothing is stored.** The session is an httpOnly cookie. `localStorage` holds
  only the theme and the sidebar state — never an extracted value, never a key.
- **Errors branch on `code`**, never on `detail`. `lib/status.ts` maps every RFC
  9457 code to a sentence, and `problemMessage` also handles FastAPI's array
  `detail`, which is a different shape.
- **Two renderings are load-bearing** and are described in
  `../API_CONTRACT_FOR_UI.md`: a scan always comes back `needs_review` with
  `scanned_document_review` and is shown as an *info* banner, not an error; and a
  field with nothing printed is absent, never zero, and reads "Not on document".

## Known gaps

Logged in `BACKEND_REQUESTS.md`, each worked around in code: `project_id`
undeclared in the schema, no response models, no document search (so ⌘K navigates
rather than searching), no counts-by-status endpoint (so two KPI cards are scoped
to the loaded page and say so), no `status` field on API keys (derived here), and
no export status endpoint.
