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

> Internal codename **FDIP**. The public name is Marinnex Lab; "FDIP" appears
> only in code and documents.

**Status:** built and tested, **not deployed**. No real customer has used it. See
[`docs/PROJECT_DOCUMENTATION.md`](docs/PROJECT_DOCUMENTATION.md) §42 for what
that means in detail, and §27 for what has and has not been measured.

## Run it

Five commands, in mock mode — no provider, no spend. Windows PowerShell;
[`docs/README_RUN.md`](docs/README_RUN.md) has the full version, including live
mode and troubleshooting.

```powershell
pip install -e ..\Toolkits_Management; pip install -e ".[dev]"
Copy-Item .env.example .env          # then set FDIP_KEY_PEPPER to anything long
python -m alembic upgrade head; python -m fdip.cli seed
uvicorn fdip.api.app:app --port 8000 # terminal 1
python -m fdip.worker                # terminal 2
```

Then `cd web; npm install; npm run dev` and sign in as `dev@fdip.local` /
`devpass`.

The server refuses to start without `FDIP_KEY_PEPPER`. That is deliberate: a
generated one would silently invalidate every API key already issued.

## Checks

```powershell
python -m pytest -q
python -m ruff check fdip tests
python -m mypy fdip --exclude 'tests'
cd web; npm run build
```

CI runs all four on every push and pull request.

## Documentation

| Document | What it is for |
|---|---|
| [`docs/PROJECT_DOCUMENTATION.md`](docs/PROJECT_DOCUMENTATION.md) | The whole system: architecture, data, AI, security, risks, readiness |
| [`docs/README_RUN.md`](docs/README_RUN.md) | Running it locally, end to end |
| [`docs/API_CONTRACT_FOR_UI.md`](docs/API_CONTRACT_FOR_UI.md) | What a UI or an integrator needs to know about the API |
| [`docs/QUALITY_GATE.md`](docs/QUALITY_GATE.md) | UX and accessibility evidence |
| [`docs/BACKEND_REQUESTS.md`](docs/BACKEND_REQUESTS.md) | API gaps found while building the UI; five still open |
| [`docs/CLEANUP_PLAN.md`](docs/CLEANUP_PLAN.md) | The repository tidy-up and its reasoning |
| [`docs/prompts/`](docs/prompts/) · [`docs/ux/`](docs/ux/) · [`docs/archive/`](docs/archive/) | Prompts in use · the UX package · superseded material |

The architecture and its frozen decisions live in `CLAUDE.md`, one directory
above this repository.

## Layout

```
fdip/          the Python package: domain, pipeline, adapters, api
migrations/    Alembic
tests/         13 files
samples/       five sample documents and a captured API response set
web/           React UI, with its own README and dev scripts
docs/          everything written down
```
