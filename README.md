# Marinnex Lab

Reads Malaysian supplier invoices and hands back structured data, showing where
every value came from.

Upload an invoice and each field comes back with the words on the page it was
read from. Anything that cannot be pointed at, or that fails an arithmetic
check, waits for a person instead of being passed on. Pick the fields you want,
pin them as a schema version, create an API key, and your own code receives the
same JSON.

The design rule is **AI proposes, deterministic code decides**: two bounded model
calls — classify, then extract — and everything after them is ordinary code.

> Internal codename **FDIP**. The public name is Marinnex Lab; "FDIP" appears in
> code, routes, configuration and documents, and this README uses both.

**Status: built and tested, not deployed.** No real customer has used it, and
nothing has been deployed to any server. The AWS instructions here are written
from the configuration in `deploy/` and were verified by building and running
the stack locally under Docker Desktop — not by running it on EC2.
[`docs/PROJECT_DOCUMENTATION.md`](docs/PROJECT_DOCUMENTATION.md) §42 lists what
is still open; §27 lists what has and has not been measured.

**Licence: proprietary, all rights reserved.** This repository is public so the
work can be read and assessed. That is not a grant of rights to run it for
yourself or for anyone else — read [Licence](#licence) before deploying
anything.

---

## Contents

- [What it does](#what-it-does)
- [How it works](#how-it-works)
- [Stack](#stack)
- [Repository structure](#repository-structure)
- [Prerequisites](#prerequisites)
- [Quick start: the UI alone, no backend](#quick-start-the-ui-alone-no-backend)
- [Local development: the whole system](#local-development-the-whole-system)
- [Configuration](#configuration)
- [Database and migrations](#database-and-migrations)
- [Provider modes and cost](#provider-modes-and-cost)
- [External services you have to supply](#external-services-you-have-to-supply)
- [Verifying it works](#verifying-it-works)
- [A full workflow](#a-full-workflow)
- [Production deployment](#production-deployment)
- [Backups](#backups)
- [Logging and troubleshooting](#logging-and-troubleshooting)
- [Upgrades](#upgrades)
- [Security](#security)
- [Limitations](#limitations)
- [Documentation](#documentation)
- [Contributing](#contributing)
- [Licence](#licence)

---

## What it does

| | |
|---|---|
| **Evidence for every value** | Each extracted field carries the page, the bounding box and the words it was read from — including each cell of each line item. |
| **Deterministic validation** | Required fields, formats, `subtotal + tax = total`, `rate × base ≈ amount`, line totals against the subtotal. The model never does arithmetic. |
| **Routing by grounding, not confidence** | A value that cannot be located among the document's own words goes to a person. |
| **Interactive and pipeline modes** | Pick fields in the UI and pin them as an immutable schema version; then `POST /v1/extract` with an API key returns the same shape to your own code. |
| **Malaysian invoices first** | MYR, SST, day-first dates, bilingual English and Malay labels. Credit notes as a variant. |
| **Digital PDFs and scans** | A text layer is read with pdfplumber; a scan or photo is read with Tesseract at 300 DPI. One API over both. |
| **Immutable history** | Schema versions and extractions are never updated. A correction writes version *n+1* and an audit event. |
| **Reproducible** | Every extraction records the schema, template, provider, model, prompt, classifier and pipeline versions, plus the document hash. |

## How it works

Twelve stages, of which exactly two call a model.

```
upload → hash, store, create a job
       → probe: pages, encryption, text coverage, rotation
       → route each page: text layer → pdfplumber | image → Tesseract OCR
       → parse in a sandboxed subprocess → words in reading order
       → classify ......................................... MODEL CALL 1
       → type gate (pipeline mode only)
       → extract against the schema version ............... MODEL CALL 2
       → ground: find every value among the document's words
       → validate: required, formats, arithmetic, cross-field
       → decide: completed | needs_review
       → review in the UI → a correction writes a new version
       → export (CSV, Excel) or API response
```

Grounding is the part that matters. The model proposes a value; deterministic
code then has to find it on the page.

| Match class | Meaning | Effect |
|---|---|---|
| `exact` | Equals a run of consecutive whole words on one page | Accept if validators pass |
| `normalized` | Equal after normalising separators, currency symbols, case or date format | Accept if validators pass |
| `derived` | Not on the page, but equals a computation the schema permits | Accept only where the field allows it |
| `fuzzy_ocr` | One edit away from a low-confidence OCR word | Review: "possible OCR misread" |
| `not_found` | None of the above | Review. The strongest hallucination signal there is |
| `not_checked` | Booleans and containers, which have nothing to match | — |

A job ends `completed` only if every required field is grounded, the schema
validates, every validator passes and there is no critical warning. Otherwise it
is `needs_review`, with a reason for each field. The rule is versioned, so a
decision made last month can be explained with the rule that made it.

**There is no calibrated per-field confidence in this system**, so the UI never
shows a percentage. It shows verification states — grounded, needs review, not
on document — because a number nobody has calibrated is a number someone would
trust.

## Stack

| Layer | What |
|---|---|
| API | FastAPI, uvicorn, one process. 33 routes under `/v1`, RFC 9457 problem details with a machine-readable `code` |
| Worker | One process, `python -m fdip.worker`. Durable per-stage checkpoints, so a crash replays at most one stage and never repeats a paid model call |
| Database | SQLite in WAL mode, SQLAlchemy Core (no ORM), Alembic. 21 tables, every row carrying `project_id` |
| Storage | A local folder behind a port; S3 is the documented swap |
| Frontend | Vite 8, React 19, TypeScript 5.9, Tailwind v4, TanStack Query, openapi-fetch, Radix, cmdk |
| AI provider | DeepSeek (`deepseek-flash`) over an OpenAI-compatible HTTP API. A configuration value, never hard-coded; Amazon Bedrock Nova is the documented switch |
| Parsing | pdfplumber for text layers, Tesseract for OCR, pypdfium2 for rendering |
| Shared toolkit | [`Toolkits_Management`](https://github.com/RoycenChew/Toolkits_Management) v0.9.0, a **separate repository** — see [Prerequisites](#prerequisites) |
| Production | Docker Compose: Caddy, API, worker, Litestream, on one small Linux server |

It is a **modular monolith** on purpose: one API process, one worker, one SQLite
file. No Redis, no Celery, no Kubernetes, no microservices. Everything runs on a
laptop, and nothing in the domain layer imports a web framework or a database —
a test enforces the import graph.

## Repository structure

```
fdip/                     the Python package
  domain/                 pure: schema language, templates, money, validators, decision rule
  pipeline/               the twelve stages above, on durable checkpoints
  adapters/               storage, SQLite repository, sandbox runner, provider config, keys
  api/                    FastAPI routers, auth, rate limits, problem details
  worker.py cli.py config.py
migrations/               Alembic: three versions
tests/                    13 test modules, 156 tests
samples/                  five sample documents, plus 21 captured API responses
web/                      the React UI, with its own README
deploy/                   production Compose, Caddy, Litestream, operator scripts
docs/                     everything written down
openapi.json              the API contract; a test fails if it drifts from the code
Dockerfile                development image for the API and worker
docker-compose.yml        development API and worker. No UI service — see the note below
```

---

## Prerequisites

| | Version | Needed for | Notes |
|---|---|---|---|
| Python | **3.11 or later** | backend | 3.13 is what CI uses |
| Node.js | **22 or later** | frontend | CI pins 22 |
| Git | any | both | the toolkit is a second checkout |
| Tesseract OCR | 5.x | scanned documents only | a binary; pip cannot install it. Digital PDFs do not need it |
| Docker | Desktop 4.x, or Engine 24+ with Compose v2 | the production stack only | not needed for local development |

### The shared toolkit

**It is a separate repository and is deliberately not declared as a Python
dependency.** This is the thing a fresh clone most often gets wrong. You need
`Toolkits_Management` at tag **v0.9.0**, by either route:

```bash
# Route 1 — a sibling checkout, editable. What the author uses, and what the
# Docker builds expect, because Docker cannot copy from above its own context.
git clone https://github.com/RoycenChew/Toolkits_Management
cd Toolkits_Management && git checkout v0.9.0 && cd ..
# then, from this repository:
pip install -e ../Toolkits_Management

# Route 2 — straight from the tag. What CI uses.
pip install "toolkit @ git+https://github.com/RoycenChew/Toolkits_Management@v0.9.0"
```

With route 1, lay the two checkouts out as siblings:

```
<your workspace>/
  Marinnex/               this repository
  Toolkits_Management/    the toolkit, at tag v0.9.0
```

The Docker builds under `deploy/` assume exactly that, and assume this
repository's folder is named `Marinnex`. If yours is named something else, pass
`APP_DIR` — see [Production deployment](#production-deployment).

### pdfplumber, which nothing installs for you

```bash
pip install "pdfplumber>=0.11" "pillow>=10.0"
```

The toolkit's base install is standard-library only by design, and `pdfplumber`
lives in an extra that also pulls in hundreds of megabytes this project never
uses. So it has to be installed by name.

**Without `pdfplumber` the API starts, uploads are accepted, and every document
fails at the parse stage** — `status=failed`, with the unhelpfully generic code
`internal`. Measured: the same sample document returns `completed` with the
package installed and `failed` without it. `pillow` is needed for the scan
route. `deploy/Dockerfile.app` installs both by name for the same reason, and CI
installs `pdfplumber` as its own step.

### Tesseract

```powershell
# Windows: install from https://github.com/UB-Mannheim/tesseract/wiki, then
tesseract --version
```

```bash
# Debian or Ubuntu. The Malay pack matters: a Malaysian invoice is routinely
# bilingual, and English data alone loses half the labels.
sudo apt-get install -y tesseract-ocr tesseract-ocr-eng tesseract-ocr-msa
tesseract --version
```

Without the binary, scanned images and scanned PDFs fail with a clear message,
digital PDFs are unaffected, and one test module skips itself.

---

## Quick start: the UI alone, no backend

The fastest honest look at the product. No Python, no provider, no spend: the
whole app is served from 21 API responses captured from a real run.

```bash
cd web
npm install
npm run dev
```

Open <http://localhost:5173>. Sign in with anything — the mock layer accepts it.

This works because `web/.env.development` is committed and sets
`VITE_USE_MOCKS=true`, so a plain `npm run dev` **never contacts a backend**.
That is deliberate, and it is also a trap: starting a backend and then running
`npm run dev` appears to work while talking to nothing at all. To use the real
API, see step 8 below.

---

## Local development: the whole system

Four processes, and the order matters. Commands are given for PowerShell and for
bash where they differ.

### 1. Clone both repositories

```bash
git clone https://github.com/RoycenChew/Marinnex
git clone https://github.com/RoycenChew/Toolkits_Management
cd Toolkits_Management && git checkout v0.9.0 && cd ../Marinnex
```

### 2. A virtual environment

```powershell
# PowerShell, from the Marinnex folder
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

```bash
# bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

If PowerShell blocks activation:
`Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`.

### 3. Install

```bash
pip install -e ../Toolkits_Management
pip install -e ".[dev]"
pip install "pdfplumber>=0.11" "pillow>=10.0"
```

The third line is not optional — see [Prerequisites](#prerequisites).

### 4. Configure

```powershell
Copy-Item .env.example .env       # PowerShell
```

```bash
cp .env.example .env              # bash
```

Then set two secrets in `.env`. **The server refuses to start without
`FDIP_KEY_PEPPER`, in every mode.** That refusal is the design: a generated
pepper would silently invalidate every API key already issued, with nothing in
the logs to say why.

```ini
FDIP_PROVIDER_MODE=mock
FDIP_KEY_PEPPER=<32+ random characters>
FDIP_SESSION_SECRET=<32+ random characters>
```

Generate them:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

`.env` is git-ignored and must never be committed. Everything below runs in
**mock mode**: no provider, no network, no spend.

### 5. Create the database and seed it

```bash
python -m alembic upgrade head
python -m fdip.cli seed
```

That creates `data/fdip.db`, seeds the 26-field invoice template, and — because
`FDIP_DEV_SEED=1` and the mode is not live — a development account:

```
dev@fdip.local / devpass     project: Default
```

**The development account is never created in live mode**, whatever
`FDIP_DEV_SEED` says. A known password in a deployed system is not a
convenience. For a real deployment, see [Inviting people](#inviting-people).

### 6. Check the pipeline before starting any server

The fastest way to tell whether a problem is in the pipeline or in the API, so
run it first.

```bash
python -m fdip.cli run samples/invoice_digital.pdf --schema invoice@1
```

It prints the document type, the status, token counts, and one line per field
with its match class and evidence page. It prints **no extracted values** unless
you add `--show-values`, because a terminal scrollback is a log. The installed
console script does the same: `fdip run samples/invoice_digital.pdf`.

### 7. The API and the worker

Two terminals, both with the virtual environment active.

```bash
# terminal 1
uvicorn fdip.api.app:app --reload --port 8000

# terminal 2
python -m fdip.worker
```

| URL | What |
|---|---|
| <http://localhost:8000/v1/health> | database, worker heartbeat age, pipeline version |
| <http://localhost:8000/v1/docs> | Swagger UI, every route |
| <http://localhost:8000/v1/openapi.json> | the live contract |

**The API alone will accept uploads and leave them `processing` forever.** The
worker is what moves them. Start both.

### 8. The UI against the real API

```powershell
cd web
npm install
$env:VITE_USE_MOCKS = "false"
npm run dev
```

```bash
cd web
npm install
VITE_USE_MOCKS=false npm run dev
```

Open <http://localhost:5173> and sign in as `dev@fdip.local` / `devpass`.

Port 5173 is the only origin in `FDIP_CORS_ORIGINS` by default. The session is
an httpOnly cookie, so CORS runs with credentials allowed — which means a
wildcard origin cannot work and the list is not optional. Add others as a
comma-separated list.

[`web/README.md`](web/README.md) covers the frontend on its own: scripts,
design tokens, conventions and mock fixtures.

---

## Configuration

All backend configuration comes from the environment, or from a git-ignored
`.env` read at startup. **The shell wins over `.env`**, so an exported value is
always the operator's explicit choice. Copy
[`.env.example`](.env.example) and work from it.

### Read by the application

| Variable | Default | Required | What it does |
|---|---|---|---|
| `FDIP_KEY_PEPPER` | — | **always**, ≥16 chars | HMAC pepper for API key hashes. The server refuses to start without it |
| `FDIP_SESSION_SECRET` | generated | in `live` and `production`, ≥16 chars | Signs session cookies. A generated one logs everyone out on restart |
| `FDIP_PROVIDER_MODE` | `mock` | no | `mock`, `recorded` or `live`. See [Provider modes](#provider-modes-and-cost) |
| `DEEPSEEK_API_KEY` | empty | in `live` and `production` | The provider key. Never logged, never echoed |
| `TOOLKIT_MODEL` | `deepseek-flash` | no | The model id passed to the provider |
| `FDIP_AI_MONTHLY_CEILING_USD` | `20` | in `production` | A hard monthly spend ceiling, enforced against real priced usage |
| `FDIP_ENV` | `development` | no | `production` turns on the startup refusals in the table below |
| `FDIP_DATA_DIR` | `./data` | no | Blobs, exports, checkpoints and the LLM cache |
| `FDIP_DB_URL` | `sqlite:///./data/fdip.db` | no | SQLAlchemy URL. SQLite is the only tested backend |
| `FDIP_CORS_ORIGINS` | `http://localhost:5173` | no | Comma-separated. Credentials are allowed, so no wildcard |
| `FDIP_ALLOW_REGISTRATION` | `true` | no | `false` makes `/v1/auth/register` answer 403 and the UI hide its sign-up link |
| `FDIP_DEV_SEED` | `1` outside `live` | no | Seeds `dev@fdip.local`. Ignored in live mode entirely |
| `FDIP_SCAN_AUTO_ACCEPT` | `false` | no | Leave it false. See [Limitations](#limitations) |
| `FDIP_EXTRACT_THINKING_DIGITAL` | `on` | no | `on`, `off` or `repair` — provider reasoning on the text-layer route |
| `FDIP_EXTRACT_THINKING_SCAN` | `repair` | no | The same, on the OCR route |
| `FDIP_EXTRACT_THINKING` | unset | no | Overrides both of the above when set |
| `FDIP_LOGIN_ATTEMPTS_PER_MINUTE` | `10` | no | Per calling address |
| `FDIP_UPLOADS_PER_MINUTE` | `30` | no | Per calling address; uploads and `/v1/extract` share it |

Not environment variables, but worth knowing — these are fixed in
`fdip/config.py`: a 20 MB upload limit, a 25-page limit, a 60-second sandbox
timeout, a 90-second model timeout, a five-minute job lease, 60 requests a
minute per API key, and a 16,000-token extraction cap.

### Read only by the deployment

These are consumed by `deploy/docker-compose.prod.yml`, the Caddyfile and the
operator scripts. The application never reads them.

| Variable | Default | What it does |
|---|---|---|
| `DOMAIN` | — | The hostname Caddy obtains a certificate for. `localhost` makes it issue an internal one |
| `BACKUP_BUCKET` | — | S3 bucket for Litestream and the nightly file sync |
| `AWS_REGION` | `ap-southeast-5` | Region for SSM and S3 |
| `DATA_DIR` | `/srv/marinnex/data` | Host path bind-mounted at `/data` |
| `APP_DIR` | `Marinnex` | The folder this repository is checked out into |
| `MARINNEX_ROOT` | `/srv/marinnex` | Where `deploy.sh` expects both checkouts |
| `TOOLKIT_TAG` | `v0.9.0` | The toolkit tag `deploy.sh` checks out |
| `SSM_PREFIX` | `/marinnex/prod` | Where `fetch-secrets.sh` reads from |
| `ENV_FILE` | `/srv/marinnex/.env` | Where `fetch-secrets.sh` writes |

### Build-time, frontend

Baked into the bundle by Vite at build time, not read at runtime.

| Variable | Default | What it does |
|---|---|---|
| `VITE_USE_MOCKS` | `true` in development | `true` serves the whole app from MSW with no backend |
| `VITE_API_BASE` | `http://localhost:8000` | The API **origin only** — the generated paths already begin with `/v1`. An explicitly empty value means same origin, which is what the production image sets |

`VITE_API_BASE` is read with `??`, not `||`, so empty and unset mean different
things. That distinction is load-bearing: with `||`, an empty value fell through
to the development default, the deployed bundle called `http://localhost:8000`,
and the CSP blocked it — "Failed to fetch" on sign-in, with nothing in the server
logs, because the request never left the browser.
`deploy/Dockerfile.web` now fails the build if the string `localhost:8000`
appears anywhere in `dist/`.

### What `FDIP_ENV=production` changes

| Setting | Development | Production |
|---|---|---|
| `FDIP_PROVIDER_MODE=mock` | the default | **refused at startup** |
| `FDIP_SESSION_SECRET` | generated if absent | **required** |
| `DEEPSEEK_API_KEY` | optional | **required** |
| `FDIP_AI_MONTHLY_CEILING_USD` | defaults to 20 | **required** |
| `FDIP_KEY_PEPPER` | required | required |
| Registration | open | closed, by convention — set `FDIP_ALLOW_REGISTRATION=false` |

Every one of those is checked **at startup**, not at the first request. A server
that starts without a pepper and quietly invalidates every API key is worse than
one that will not start.

---

## Database and migrations

SQLite in WAL mode, created by Alembic. Three migrations, 21 tables, every row
carrying `project_id` — the repository layer refuses an unscoped query.

```bash
python -m alembic upgrade head      # create or update the schema
python -m alembic current           # which revision is applied
python -m alembic history           # all three
```

There is no automatic migration on startup, deliberately. In production,
`deploy/scripts/deploy.sh` runs `alembic upgrade head` in a **one-off container
before anything serves traffic**, because running migrations from the API's
start command would race two uvicorn workers against each other on a single
SQLite file.

**One writer at a time.** SQLite allows exactly one, which is why there is one
worker process and not two. A `database is locked` error almost always means a
second worker is running.

Schema versions and extractions are never updated in place. A correction writes
a new extraction version and an audit event, so the original stays readable.

---

## Provider modes and cost

`FDIP_PROVIDER_MODE` takes three values.

| Mode | Behaviour |
|---|---|
| `mock` | Scripted answers from fixtures. No network, no spend. Never reads the document. The default, and what tests and CI use |
| `recorded` | Replays a local SQLite cache of real responses. **A cache miss is an error, not a request**, so a changed prompt cannot start spending by accident. This is what a demo should use |
| `live` | Real DeepSeek calls, under the monthly ceiling |

For live:

```powershell
$env:FDIP_PROVIDER_MODE = "live"
$env:DEEPSEEK_API_KEY = "sk-..."
$env:FDIP_AI_MONTHLY_CEILING_USD = "20"
python -m fdip.cli run samples\invoice_digital.pdf
```

One digital invoice costs about **US$0.0035** at peak and half that off-peak
(measured over 420 documents in the Phase 1 benchmark). The ceiling is enforced
against real priced usage: without a price book the governor refuses to pretend
a limit is binding, so a misconfiguration fails loudly rather than running
uncapped.

A `fdip_test_` API key is forced onto a non-live provider whatever the mode says.
That is the point of having two key schemes.

**Production refuses `mock` at startup.** Mock mode answers from canned
fixtures, which in front of real users is invented data that looks exactly like
a real extraction — the worst failure this product could have.

---

## External services you have to supply

None of the author's accounts, buckets, keys, domains or servers are reachable
from here. For a real deployment you need your own:

| Service | Needed for | Notes |
|---|---|---|
| **DeepSeek API key** | any live extraction | <https://platform.deepseek.com>. The only paid dependency. Amazon Bedrock Nova is the documented alternative, and the provider is a configuration value |
| **A Linux server** | hosting | The stack is sized for 2 vCPU / 2 GB — an EC2 `t3.small` in `ap-southeast-5` is what `deploy/` is written for, but any Ubuntu 24.04 box with Docker works |
| **A domain name** | HTTPS | An A record pointing at the server, with ports 80 and 443 open. Caddy needs both to obtain a certificate |
| **An S3 bucket** | backups | For Litestream and the nightly file sync. Optional if you accept having no backups |
| **An IAM instance role** | backups and secrets | So no AWS keys exist on the box: `s3:PutObject/GetObject/DeleteObject/ListBucket` on the bucket, and `ssm:GetParametersByPath` + `kms:Decrypt` if you use SSM |
| **AWS SSM Parameter Store** | secrets | Optional. `fetch-secrets.sh` reads from it; you can write `.env` by hand instead |

Runs locally, nothing to supply: the database (SQLite file), file storage (a
folder), the job queue (a table), rate limiting (in-process) and sessions
(signed cookies).

**Data residency.** Files, database and backups stay on your server or in your
own S3 bucket. AI processing happens at the provider — DeepSeek stores data in
China — so a privacy notice has to say so. A Malaysian PDPA review of
cross-border transfer is an open release blocker, not a solved problem.

---

## Verifying it works

The four checks CI runs on every push and pull request. All four must be clean.

```powershell
python -m pytest -q                       # 156 tests
python -m ruff check fdip tests
python -m mypy fdip --exclude 'tests'
cd web; npm run build                     # tsc -b, then vite build
```

The suite never contacts a provider: it runs in mock mode with a temporary data
directory per test. One module is marked `live`, and `pytest`'s own
configuration excludes it, so a bare `pytest` cannot spend money — it also needs
`FDIP_LIVE_SMOKE=1`, because a marker alone is one typo away from a bill.

Then a round trip against a running API:

```bash
curl -c cookies.txt -X POST http://localhost:8000/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"dev@fdip.local","password":"devpass"}'

curl -b cookies.txt -X POST http://localhost:8000/v1/documents \
  -F "file=@samples/invoice_digital.pdf"

# then poll, with the document_id from that response
curl -b cookies.txt http://localhost:8000/v1/documents/<document_id>
```

The frontend has four more checks, which need Playwright browsers installed
(`npx playwright install chromium`) and a dev server running:

```bash
cd web
npm run lint
npm run check:a11y        # axe-core, every screen
npm run check:contrast
npm run check:keyboard
```

The five sample documents are there to be used: `invoice_digital.pdf`,
`invoice_malay.pdf` (Malay labels, SST 6%), `credit_note.pdf` (negative
amounts), `invoice_scanned.png` (a 200 DPI scan, needs Tesseract) and
`not_an_invoice.pdf` (a bank statement, for the type gate).

---

## A full workflow

What the product is for, end to end. Mock mode is enough to walk all of it.

1. **Upload** `samples/invoice_digital.pdf` on the Documents screen. It returns
   `202` with a `document_id` and a `job_id`; the worker picks it up. The same
   file uploaded twice in one project is the same document, by hash, and
   `POST /v1/documents` takes an `Idempotency-Key` header so a retried request
   returns the original job rather than a second one.
2. **Watch it process.** `GET /v1/jobs/{id}` reports the stage. A digital
   invoice takes a few seconds in mock mode.
3. **Review the evidence.** The review screen draws the page and highlights the
   words each value came from. A field with nothing printed on the document is
   absent, not zero, and reads "Not on document".
4. **Correct anything wrong.** A correction writes extraction version *n+1* and
   an audit event. The original is never overwritten.
5. **Approve or reject.** Either way it is recorded against your account, and
   visible on your account page.
6. **Pick your fields and pin a schema version.** Choose from the 26-field
   invoice template, or build a custom schema. The version is immutable, and
   `GET /v1/schemas/{id}/versions/{v}/contract` gives you its JSON Schema — the
   contract your own code can validate against.
7. **Run a schema test** on three to five sample documents. This is required
   before an API key may use that version: a key pointed at an untested schema
   is a pipeline nobody has ever seen succeed.
8. **Create an API key.** Shown **once** and never again — only
   `HMAC-SHA256(pepper, secret)` is stored. Use `fdip_test_` keys while
   integrating: they are forced onto a non-live provider and cost nothing.
9. **Call it from your own code.**

   ```bash
   curl -X POST https://your-domain/v1/extract \
     -H "Authorization: Bearer fdip_live_..." \
     -F "file=@invoice.pdf" \
     -F "schema_id=invoice" \
     -F "schema_version=3"
   ```

   You get `202` and an `extraction_id`; add `?wait=30` to get `200` with the
   result if it finishes in time. Poll `GET /v1/extractions/{id}` until the
   status is terminal. `needs_review` is a real answer, not an error: it carries
   provisional data plus a reason for each field, and resolves when a person
   has looked.
10. **Export** to CSV or Excel, or read `GET /v1/usage` for pages and AI cost
    per key per month.

Errors are RFC 9457 problem documents. **Branch on `code`, never on `detail`** —
`unsupported_file_type`, `encrypted_pdf`, `page_limit_exceeded`,
`document_type_mismatch`, `schema_version_not_allowed`, `quota_exceeded`,
`rate_limited`. [`docs/API_CONTRACT_FOR_UI.md`](docs/API_CONTRACT_FOR_UI.md) has
the full list with real captured examples.

---

## Production deployment

> Read [Licence](#licence) first. Operating this software requires written
> permission; what follows is a complete account of how, not a grant of rights.

One Ubuntu 24.04 server, four containers, a SQLite file replicated to S3. Sized
for a `t3.small`. [`docs/DEPLOY.md`](docs/DEPLOY.md) is the operator's version of
this section with more detail.

| Container | What it does | Memory limit |
|---|---|---|
| `caddy` | TLS, serves the built SPA, proxies `/v1/*` to the API | 128 MB |
| `api` | uvicorn, 2 workers | 768 MB |
| `worker` | the document pipeline | 768 MB |
| `litestream` | continuous replication of the database to S3 | 128 MB |

1.7 GB of limits on a 2 GB box, plus a 2 GB swap file as a safety net for a
300 DPI render spike. The API and the worker share **one image**: same code,
different command, because two images would be two things to keep in step.

### The build context is the parent directory

Both production images copy the toolkit from a sibling folder, and Docker cannot
copy from above its own context. So the context is the **parent** of this
repository, and the repository's folder name is passed in as `APP_DIR`:

```
/srv/marinnex/                  <- the build context, and MARINNEX_ROOT
  Marinnex/                     <- this repository (APP_DIR)
  Toolkits_Management/          <- the toolkit at v0.9.0
  .env                          <- secrets, mode 600, never in git
```

### First time

```bash
# on the server, as a user with sudo
curl -fsSL https://raw.githubusercontent.com/RoycenChew/Marinnex/main/deploy/setup-server.sh -o setup-server.sh
bash setup-server.sh
# log out and back in, so the docker group applies

git clone https://github.com/RoycenChew/Marinnex              /srv/marinnex/Marinnex
git clone https://github.com/RoycenChew/Toolkits_Management    /srv/marinnex/Toolkits_Management

/srv/marinnex/Marinnex/deploy/scripts/deploy.sh
```

`setup-server.sh` creates the swap file, installs Docker and the AWS CLI, turns
on unattended security upgrades, creates `/srv/marinnex/data` owned by uid 10001
(the non-root user inside the image), and schedules the nightly file backup.

### Secrets

`deploy.sh` calls `fetch-secrets.sh`, which writes `/srv/marinnex/.env` from AWS
SSM Parameter Store under `/marinnex/prod`, one parameter per line, mode 600,
never echoing a value. Store these as `SecureString`:

| Parameter | Example |
|---|---|
| `FDIP_KEY_PEPPER` | 32+ random characters |
| `FDIP_SESSION_SECRET` | 32+ random characters |
| `DEEPSEEK_API_KEY` | your provider key |
| `FDIP_AI_MONTHLY_CEILING_USD` | `20` |
| `FDIP_ALLOW_REGISTRATION` | `false` |
| `DOMAIN` | `app.example.com` |
| `BACKUP_BUCKET` | `your-backup-bucket` |

**Without SSM:** write `/srv/marinnex/.env` by hand with the same variables,
`chmod 600` it, and skip `deploy.sh` in favour of the four commands it runs:

```bash
cd /srv/marinnex
COMPOSE="docker compose -f Marinnex/deploy/docker-compose.prod.yml --env-file .env"
$COMPOSE build
$COMPOSE run --rm --no-deps api python -m alembic upgrade head
$COMPOSE up -d --remove-orphans
curl -fsS http://localhost/v1/health
```

[*Recommended, not verified: the individual commands are taken from
`deploy.sh`, and the stack has been built and run locally this way, but no
SSM-free deployment has been performed on a server.*]

### Every release after that

```bash
/srv/marinnex/Marinnex/deploy/scripts/deploy.sh
```

It pulls both repositories, checks the toolkit out at **`v0.9.0`** (pinned, not
latest — a deployment that silently picked up newer toolkit code would be a
different system from the one that was tested), fetches secrets, builds, runs
migrations in a one-off container, starts everything, and polls `/v1/health` for
five minutes. It exits non-zero and prints the last 40 log lines if the service
never becomes healthy. Every step is idempotent, so it is safe to re-run.

### Inviting people

Registration is closed in production, so `/v1/auth/register` answers `403` with
a message a person can act on, and the UI hides the sign-up link and says
"invite only" rather than leaving someone to guess.

```bash
/srv/marinnex/Marinnex/deploy/scripts/create-user.sh someone@example.com
```

It generates a 24-character temporary password and prints it **once**. Pass it
on directly; it is never mailed or logged. The account comes with a project,
because an account with no project is a dead end the UI cannot escape.

**There is no forgotten-password email and no reset link.** A user can change
their own password on their account page, with their current password. If they
lose it, an operator resets it by hand:

```bash
/srv/marinnex/Marinnex/deploy/scripts/reset-password.sh someone@example.com
```

### Domain and HTTPS

Point an A record at the server, open 80 and 443, and set `DOMAIN`. Caddy
obtains and renews a Let's Encrypt certificate automatically; with
`DOMAIN=localhost` it issues an internal certificate instead, so a local run
shows a browser warning. The `caddy-data` volume holds the certificates and the
ACME account key — losing it means re-issuing on every restart, which
Let's Encrypt rate-limits.

At the edge, Caddy sets HSTS for a year, `X-Content-Type-Options: nosniff`,
`X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, and
a CSP allowing only this origin plus `data:` and `blob:` images (the page images
the review screen draws). No inline script, no CDN: everything the app needs is
in the bundle. Bodies over **20 MB** are refused at the edge, matching the
application's own limit — note the client sees a connection reset rather than a
clean `413`, because Caddy stops reading rather than replying.

### Trying the production stack locally

Docker Desktop, from the parent of this repository:

```bash
cd ..                                   # the folder holding both checkouts
cp Marinnex/.env.example .env           # set DOMAIN=localhost and a pepper
docker compose -f Marinnex/deploy/docker-compose.prod.yml --env-file .env up --build -d
docker compose -f Marinnex/deploy/docker-compose.prod.yml --env-file .env \
  run --rm --no-deps api python -m alembic upgrade head
```

If your clone is not named `Marinnex`, add `APP_DIR=<your-folder>` to `.env`.
To exercise the stack without a provider key, override the environment for that
run only — production normally forbids it:

```bash
FDIP_ENV=development FDIP_PROVIDER_MODE=mock \
  docker compose -f Marinnex/deploy/docker-compose.prod.yml --env-file .env up --build -d
```

### The development Docker files are not this

`Dockerfile` and `docker-compose.yml` at the repository root are a development
convenience: API and worker only, **no UI service**, no TLS, a named volume
instead of a bind mount. The supported local path is the two processes in
[step 7](#7-the-api-and-the-worker). For anything resembling production, use
`deploy/docker-compose.prod.yml`.

---

## Backups

Two separate things, because they fail differently.

**The database** is replicated continuously by Litestream to
`s3://$BACKUP_BUCKET/litestream/fdip.db`: a snapshot a day, WAL frames in
between, seven days of retention.

**The uploaded files** are synced nightly at 03:15 UTC by `backup-files.sh` to
`s3://$BACKUP_BUCKET/files/`. Restoring the database without the files gives you
a catalogue of documents nobody can open.

```bash
BACKUP_BUCKET=your-backup-bucket /srv/marinnex/Marinnex/deploy/scripts/restore-test.sh
```

That restores the latest copy into a temporary folder, runs SQLite's own
`integrity_check` and prints row counts. It warns if the restored database is
empty, which proves the pipe works and not that the data is there. **A backup
nobody has restored is a hypothesis.** Run it after the first real documents
arrive, and periodically after that.

---

## Logging and troubleshooting

Logs are structured JSON carrying **ids and codes only**. They deliberately
contain no document text, no extracted values, no prompts, no model responses
and no keys. SQLAlchemy's statement logger is held at `WARNING` and detached,
because it prints bound parameters — which are the extracted data. Turning the
root logger up to `DEBUG` will not leak document content, and a test proves it.

| Symptom | Cause |
|---|---|
| Every document fails at the parse stage | `pdfplumber` is not installed — see [Prerequisites](#prerequisites) |
| Uploads stay `processing` forever | the worker is not running |
| Every scan comes back `needs_review` | expected: `FDIP_SCAN_AUTO_ACCEPT` is false by default. See [Limitations](#limitations) |
| The server will not start | it names the missing variable. That is the design, not a bug |
| `database is locked` | two writers; SQLite allows one. Look for a second worker |
| `tesseract` errors on a PNG | the binary is not on `PATH` |
| `401` on every UI call | the browser is not sending the cookie; the client needs `credentials: "include"` |
| A CORS error in the browser | the origin is not in `FDIP_CORS_ORIGINS` |
| The UI shows data with no backend running | `VITE_USE_MOCKS` is `true`, which is the development default |
| "Failed to fetch" on a deployed sign-in | the bundle was built with the development API base. `deploy/Dockerfile.web` now fails the build for this |
| `openapi.json is stale` in tests | run `fdip openapi --out openapi.json` |
| Deploy says it never became healthy | `docker compose … logs api --tail 100` |
| No certificate | the DNS A record, and ports 80/443; `docker compose … logs caddy` |
| `/v1/health` shows a large `worker_heartbeat_age_seconds` | the worker is down |
| Out of memory on the server | `free -h`; check the swap file exists and `vm.swappiness` is 10 |

---

## Upgrades

```bash
git pull
pip install -e ../Toolkits_Management        # if the toolkit tag moved
pip install -e ".[dev]"
python -m alembic upgrade head
cd web && npm ci && npm run build
```

On a server, `deploy/scripts/deploy.sh` does all of that in the right order and
refuses to report success until `/v1/health` answers.

The toolkit is pinned to **v0.9.0**. Moving that pin is a deliberate act: run
the full suite against the new tag before changing `TOOLKIT_TAG` or the CI
workflow. `openapi.json` is committed and a test fails if it drifts from the
code, so regenerate it with `fdip openapi --out openapi.json` after any route
change, and regenerate the frontend types with `npm run gen:api`.

Migrations only ever go forward in practice. Take a copy of `data/fdip.db`
before upgrading anything that matters.

---

## Security

What is already true:

- **API keys are credentials.** Format `fdip_live_<key_id>_<secret>` or
  `fdip_test_…` with a 256-bit random secret. Only
  `HMAC-SHA256(server_pepper, secret)` is stored, compared in constant time, and
  the key is shown exactly once.
- **Passwords** are hashed with Argon2, minimum eight characters, and a change
  requires the current password — a borrowed session should not become a
  permanent takeover.
- **Sessions** are signed httpOnly cookies, `SameSite=Lax`, `Secure` over HTTPS.
  No token in `localStorage`, which holds only the theme and the sidebar state.
- **Nothing sensitive is logged.** No document text, no extracted values, no
  page images, no prompts, no responses, no keys. Tested, in both development
  and production settings.
- **Untrusted input is contained.** Parsing and OCR run in a subprocess with
  wall-clock and memory limits. Uploads are capped at 20 MB and 25 pages.
  Prompt-injection text in a document is flagged, and containment is structural
  — sanitise, delimit, cap — rather than a hope that the model ignores it.
- **Rate limits** per calling address: 10 login attempts a minute, 30 uploads or
  extractions. Caddy passes `X-Forwarded-For`; without it every request would
  appear to come from the container network and one address could exhaust the
  limit for everyone.
- **Tenancy** is enforced at the repository layer: every row carries
  `project_id` and an unscoped query is refused.
- **Health** is unauthenticated on purpose — a health check behind a login is
  not one — so it reports only whether the database and worker are alive. No
  provider name, no model, no counts that would leak volume.

What is **not** done, and is a release blocker:

- **No malware scanning** on uploads.
- **No retention policy.** Documents are kept until deleted. Retention is
  configurable in principle and unset in practice.
- **No PDPA review.** Cross-border transfer to the AI provider needs a lawyer's
  opinion before real customer documents arrive.
- **No privacy notice or terms of use.**
- **Rate limiting is in-process**, which is honest for one server and wrong for
  two.

Report a security issue by opening an issue on the repository. Please do not
include a working exploit or any real document.

---

## Limitations

- **Not deployed, and no real customers.** Everything measured so far was
  measured on benchmark corpora and synthetic Malaysian invoices.
- **Scanned documents are always reviewed by a person.**
  `FDIP_SCAN_AUTO_ACCEPT` defaults to `false`, so a document whose evidence came
  from OCR never reaches `completed` automatically: it gets `needs_review` with
  the reason `scanned_document_review`. This is not a quality judgement about
  any one document. In the Phase 1 slice, the OCR route produced **13 silent
  errors in 30 mild scans**, against 0 in 30 digital ones. The suspected
  mechanism is that an OCR misread is grounded against the same misread words,
  so grounding agrees with itself and the error leaves no trace — exactly the
  failure grounding exists to catch. Do not set this to `true` until the final
  benchmark has measured that route.
- **Invoices and credit notes only.** Bank statements are the planned second
  document type and exist today only as the type gate's negative case.
- **One server, one SQLite writer.** No horizontal scaling, and the rate limiter
  and job queue are both in-process.
- **No calibrated confidence**, by design. The product shows verification states
  and never a percentage.
- **No webhooks, no SDK, no ERP connectors, no email ingestion**, and no LHDN
  e-invoice route yet.
- **English and Malay only.**
- **SQLite is the only tested database.** `FDIP_DB_URL` accepts any SQLAlchemy
  URL; nothing else has been run.
- **Open items in the API** are logged in
  [`docs/BACKEND_REQUESTS.md`](docs/BACKEND_REQUESTS.md).

---

## Documentation

| Document | What it is for |
|---|---|
| [`docs/PROJECT_DOCUMENTATION.md`](docs/PROJECT_DOCUMENTATION.md) | The whole system: architecture, data model, AI, security, risks, readiness |
| [`docs/README_RUN.md`](docs/README_RUN.md) | Running it locally on Windows, in more depth than this README |
| [`docs/DEPLOY.md`](docs/DEPLOY.md) | The operator's deployment guide |
| [`docs/API_CONTRACT_FOR_UI.md`](docs/API_CONTRACT_FOR_UI.md) | What a UI or an integrator needs from the API, with captured examples |
| [`docs/QUALITY_GATE.md`](docs/QUALITY_GATE.md) | UX and accessibility evidence |
| [`docs/BACKEND_REQUESTS.md`](docs/BACKEND_REQUESTS.md) | API gaps found while building the UI |
| [`docs/CLEANUP_PLAN.md`](docs/CLEANUP_PLAN.md) | The repository tidy-up and its reasoning |
| [`web/README.md`](web/README.md) | The frontend on its own terms |
| [`docs/prompts/`](docs/prompts/) · [`docs/ux/`](docs/ux/) · [`docs/archive/`](docs/archive/) | Prompts in use · the UX package · superseded material |

The architecture and its frozen decisions live in `CLAUDE.md`, one directory
above this repository and not part of it.

---

## Contributing

This is a single-author project with a proprietary licence, so there is no open
contribution process. Issues and questions are welcome.

If you have been given access to work on it:

- Branch from `main`. Never push to `main` directly.
- **Tests first.** Write the failing test, show it fails for the stated reason,
  then make it pass.
- All four checks in [Verifying it works](#verifying-it-works) must be clean
  before a commit, and CI runs them on every push and pull request.
- Commit messages say **what was wrong before** and how the test proves it is
  fixed.
- Regenerate `openapi.json` and `web/src/api/v1.d.ts` after any route change.
- Never log document text, extracted values, prompts, responses or keys. Never
  put an extracted value or a key in `localStorage`.
- Money is a `Decimal` end to end, serialised as a string. Never a float.
- Reusable, domain-neutral capability belongs in the toolkit, not here. Nothing
  in the toolkit may know what an invoice is.

---

## Licence

**Proprietary. Copyright © 2026 Royce Chew. All rights reserved.** See
[`LICENSE`](LICENSE).

This repository is public so the work can be read, reviewed and assessed. Being
readable is not a grant of rights. You may read the source, clone it to evaluate
it, and run it locally for that evaluation. Operating it for yourself or for
anyone else, hosting it, or deriving a work from it requires written permission.

The installation and deployment instructions above are documentation, not a
licence: they are here so a reader can verify the system does what it claims,
and so a permitted operator has a complete account of how to run it. Third-party
dependencies are governed by their own licences.
