# Running FDIP on Windows

PowerShell, Python 3.11 or later (3.13 here). From a fresh clone to a working API
and worker in under ten minutes, and the first eight of those are `pip install`.

Everything below runs in **mock mode**, which contacts no provider and spends
nothing. Switching to live is the last section, and it is one variable.

## 1. Virtual environment

```powershell
cd <the folder you cloned this repository into>
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

If activation is blocked:
`Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`.

## 2. Install

The toolkit is a sibling folder, installed editable so a change there is picked up
without reinstalling.

```powershell
pip install -e ..\Toolkits_Management
pip install -e ".[dev]"
pip install "pdfplumber>=0.11" "pillow>=10.0"
```

The third line is not optional. The toolkit's base install is standard-library
only by design, and `pdfplumber` lives in an extra that also drags in docling —
hundreds of megabytes this project never uses — so it has to be installed by
name. **Without it the API starts, uploads are accepted, and every document
fails at the parse stage** with a generic `internal` error code, which tells you
nothing about the cause. `deploy/Dockerfile.app`
installs both by name for the same reason, and CI installs `pdfplumber` as its
own step.

Scanned documents also need the Tesseract binary on `PATH`. Check with
`tesseract --version`. Without it, image files and scanned PDFs fail with a clear
message; digital PDFs are unaffected.

## 3. Configure

```powershell
Copy-Item .env.example .env
```

Then edit `.env`. For a local run the defaults are fine except the two secrets,
which you should set to anything long:

```ini
FDIP_PROVIDER_MODE=mock
FDIP_KEY_PEPPER=<32+ random characters>
FDIP_SESSION_SECRET=<32+ random characters>
FDIP_DEV_SEED=1
```

`.env` is git-ignored. **`FDIP_KEY_PEPPER` is required in every mode** — at
least 16 characters — and the server refuses to start without it. It used to be
generated outside live mode as a convenience, and the convenience was that a
local server started happily with a brand-new pepper and left every key already
in the database failing to authenticate, with nothing in the logs to say why.

`FDIP_SESSION_SECRET` is generated when absent in mock and recorded mode, and is
required in live mode and in production; a generated one logs everyone out on
restart, which is recoverable.

To generate them:

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

## 4. Migrate and seed

```powershell
python -m alembic upgrade head
python -m fdip.cli seed
```

That creates `data\fdip.db`, seeds the 26-field invoice template, and — because
`FDIP_DEV_SEED=1` and the mode is not live — a dev account:

```
dev@fdip.local / devpass     project: Default
```

The dev account is never created in live mode, whatever `FDIP_DEV_SEED` says. A
known password in a deployed system is not a convenience.

## 5. Check the pipeline without a server

This is the fastest way to tell whether a problem is in the pipeline or in the
API, so run it first.

```powershell
python -m fdip.cli run samples\invoice_digital.pdf --schema invoice@1
```

It prints the document type, the status, token counts, and one line per field with
its match class and evidence page. It prints **no extracted values** unless you
add `--show-values`: a terminal scrollback is a log, and rule 2.13 applies to it.

The installed console script works too: `fdip run samples\invoice_digital.pdf`.

## 6. Start the API and the worker

Two terminals, both with the virtual environment active.

```powershell
# terminal 1
uvicorn fdip.api.app:app --reload --port 8000

# terminal 2
python -m fdip.worker
```

Then:

- `http://localhost:8000/v1/health` — database, worker heartbeat, provider mode
- `http://localhost:8000/v1/docs` — Swagger, with every route
- `openapi.json` in this folder — the same document, for the UI agent

The API alone will accept uploads and leave them `processing` forever. The worker
is what moves them, so start both.

A quick end-to-end check with cURL:

```powershell
curl -c cookies.txt -X POST http://localhost:8000/v1/auth/login `
  -H "Content-Type: application/json" `
  -d '{\"email\":\"dev@fdip.local\",\"password\":\"devpass\"}'

curl -b cookies.txt -X POST http://localhost:8000/v1/documents `
  -F "file=@samples/invoice_digital.pdf"

# then poll, with the document_id from the response
curl -b cookies.txt http://localhost:8000/v1/documents/<document_id>
```

## 7. The UI

The UI is expected at **`http://localhost:5173`** (Vite's default), which is the
only origin in `FDIP_CORS_ORIGINS`. Add others as a comma-separated list. CORS
runs with credentials allowed, because the session is a cookie — so a wildcard
origin will not work, and the list is not optional.

A plain `npm run dev` does **not** reach this backend. `web/.env.development` is
committed and sets `VITE_USE_MOCKS=true`, so the UI serves itself from MSW
fixtures and talks to nothing. To use the real API, set
`$env:VITE_USE_MOCKS = "false"` before `npm run dev`.

The UI agent needs four things:

| File | What it is |
| --- | --- |
| `openapi.json` | the machine-readable contract; a test fails if it is stale |
| `docs/API_CONTRACT_FOR_UI.md` | the same thing for humans, with real captured examples |
| `samples\` | five documents to test against, plus `examples.json` |
| this file | how to get the backend up |

Samples: `invoice_digital.pdf`, `invoice_malay.pdf` (Malay labels, SST 6%),
`credit_note.pdf` (negative amounts), `invoice_scanned.png` (a 200 DPI scan, needs
Tesseract) and `not_an_invoice.pdf` (a bank statement, for the type gate).

**The UI can also start before this backend is running.** `samples/examples.json`
holds 21 real responses keyed by `"<METHOD> /v1/<path>"` as `{status, body}`,
captured from an actual mock-mode run, so the UI agent can work behind
`VITE_USE_MOCKS=true` and switch to the real API later. Regenerate the file with
`python -m pytest tests/test_capture_examples.py` after changing a response shape;
a test checks it stays usable as a mock source.

## 8. Tests

```powershell
python -m pytest -q
python -m ruff check fdip tests
python -m mypy fdip --exclude 'tests'
```

These are exactly what CI runs, plus `npm run build` in `web\`. Run all four
before a commit.

The suite never contacts a provider. It runs in mock mode with a temporary data
directory per test, and parsing runs in process (`FDIP_SANDBOX=0`) because
spawning a subprocess per document costs about a second on Windows; one test
exercises the real sandbox.

## 9. Provider modes

`FDIP_PROVIDER_MODE` takes three values.

| Mode | Behaviour |
| --- | --- |
| `mock` | `ScriptedLLM` from fixtures. No network, no spend. The default. |
| `recorded` | Replays the SQLite LLM cache. A **miss is an error**, not a request, so a changed prompt cannot start spending by accident. |
| `live` | Real DeepSeek calls, under the monthly ceiling. |

For live:

```powershell
$env:FDIP_PROVIDER_MODE = "live"
$env:DEEPSEEK_API_KEY = "sk-..."
$env:FDIP_AI_MONTHLY_CEILING_USD = "20"
python -m fdip.cli run samples\invoice_digital.pdf
```

One digital invoice costs about **$0.0035** at peak and half that off-peak
(`MEASURED` over 420 documents in the Phase 1 benchmark). The ceiling is enforced
against real priced usage: without a price book the governor refuses to pretend a
limit is binding, so a misconfiguration fails loudly rather than silently
uncapped.

DeepSeek's reasoning is set **per route**, because the two routes were measured
differently:

| Variable | Default | Why |
| --- | --- | --- |
| `FDIP_EXTRACT_THINKING_DIGITAL` | `on` | the only setting with a 420-document result behind it |
| `FDIP_EXTRACT_THINKING_SCAN` | `repair` | plain first attempt, reasoning on a repair |
| `FDIP_EXTRACT_THINKING` | unset | overrides both when set |

Each takes `on`, `off` or `repair`. `off` is cheapest and fastest and measured 1.7
points worse on field accuracy, which is why it is not a default anywhere.

A `fdip_test_` API key is forced onto a non-live provider whatever this is set to.
That is the point of having two key schemes.

## 9a. Scanned documents are held for review

`FDIP_SCAN_AUTO_ACCEPT=false` is the default, and it means **a document whose
evidence came from OCR never reaches `completed` automatically**: it gets
`needs_review` with the reason `scanned_document_review`.

This is not a bug and not a quality judgement about any one document. The Phase 1
slice measured **13 silent errors in 30 mild scans**, against 0 in 30 digital
ones. The suspected mechanism is that an OCR misread is grounded against the same
misread words, so grounding agrees with itself and the error leaves no trace —
exactly the failure grounding is supposed to catch.

Set it to `true` only after `run_benchmark.py --final` has measured route B. A
digital PDF with a text layer is unaffected.

## 10. Docker

`docker-compose.yml` runs the API and the worker against a shared `./data`
volume. It is optional and not the supported path on Windows; the two commands in
section 6 are.

```powershell
docker compose up --build
```

## 11. If something goes wrong

| Symptom | Cause |
| --- | --- |
| Every document fails at the parse stage | `pdfplumber` is not installed — see section 2 |
| The UI shows data with no backend running | `VITE_USE_MOCKS` is `true`, the development default |
| Every scan comes back `needs_review` | expected: `FDIP_SCAN_AUTO_ACCEPT` is false by default (see below) |
| Uploads stay `processing` | the worker is not running |
| `database is locked` | two writers; SQLite allows one. Check for a second worker |
| `tesseract` errors on a PNG | the binary is not on `PATH` |
| `401` on every UI call | the browser is not sending the cookie; set `credentials: "include"` |
| CORS error in the browser | the origin is not in `FDIP_CORS_ORIGINS` |
| `openapi.json is stale` in tests | run `fdip openapi --out openapi.json` |
| The server refuses to start, in any mode | `FDIP_KEY_PEPPER` is missing or under 16 characters |
| Live mode refuses to start | `FDIP_SESSION_SECRET` or `DEEPSEEK_API_KEY` is missing |
| `FDIP_ENV=production` refuses to start | it also needs `FDIP_AI_MONTHLY_CEILING_USD`, and forbids `FDIP_PROVIDER_MODE=mock` |

Logs are structured JSON with ids and codes only. They deliberately contain no
document text, no extracted values and no prompts — and SQLAlchemy's statement
logger is held at `WARNING` and detached, because it prints bound parameters,
which are the extracted data. Turning the root logger up to DEBUG will not leak
document content.
