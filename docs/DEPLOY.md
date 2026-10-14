# Deploying Marinnex Lab

One Ubuntu 24.04 server, four containers, a SQLite file replicated to S3. The
whole thing is meant to fit on a t3.small and be re-deployed with one command.

There is a live deployment at **<https://marinnex.duckdns.org/>**, invite only.
It is **not updated automatically**: it changes only when an operator runs
`deploy.sh` on the server, so it can lag behind `main`. Check `/v1/health` for
the `pipeline_version` it is actually running before assuming a change is on it.

The release blockers in `PROJECT_DOCUMENTATION.md` §42 are **not cleared** — no
malware scanning, no retention policy, no PDPA review, no privacy notice. That
gap is the difference between a deployment and a launch.

---

## What runs

| Container | What it does | Memory limit |
|---|---|---|
| `caddy` | TLS, serves the built SPA, proxies `/v1/*` to the API | 128 MB |
| `api` | uvicorn, 2 workers | 768 MB |
| `worker` | the document pipeline | 768 MB |
| `litestream` | continuous replication of the database to S3 | 128 MB |

1.7 GB of limits on a 2 GB box, plus a 2 GB swap file. The swap is a safety
net for a 300 DPI render spike, not slow memory — `vm.swappiness` is set to 10.

The API and the worker share **one image**: same code, different command. Two
images would be two things to keep in step.

---

## Before you start

- An EC2 instance in **ap-southeast-5** (Jakarta is the nearest region to
  Malaysia with the storage residency story §20 describes).
- An **IAM instance role**, so there are no AWS keys anywhere on the box:
  - `s3:PutObject`, `s3:GetObject`, `s3:DeleteObject`, `s3:ListBucket` on the
    backup bucket
  - `ssm:GetParametersByPath` and `kms:Decrypt` on `/marinnex/prod`
- A domain with an A record pointing at the instance, and ports 80 and 443
  open. Caddy needs both to obtain a certificate.
- The secrets in **SSM Parameter Store** under `/marinnex/prod`, as
  `SecureString` for anything secret:

  | Parameter | Example |
  |---|---|
  | `FDIP_KEY_PEPPER` | 32+ random characters |
  | `FDIP_SESSION_SECRET` | 32+ random characters |
  | `DEEPSEEK_API_KEY` | the provider key |
  | `FDIP_AI_MONTHLY_CEILING_USD` | `20` |
  | `DOMAIN` | `app.example.com` |
  | `BACKUP_BUCKET` | `marinnex-backups` |

  Generate the secrets with `python -c "import secrets;print(secrets.token_hex(32))"`.

---

## First time

```bash
# On the server, as a user with sudo. The repository is private, so clone it
# first: a plain curl of a raw file gets a 404, not a script. That needs a
# deploy key or a fine-grained token on the box, and deploy.sh runs `git pull`
# on every release, so it has to keep working unattended.
sudo mkdir -p /srv/marinnex && sudo chown "$USER" /srv/marinnex
git clone <marinnex-url>                      /srv/marinnex/Marinnex
git clone https://github.com/RoycenChew/Toolkits_Management \
                                              /srv/marinnex/Toolkits_Management

bash /srv/marinnex/Marinnex/deploy/setup-server.sh
# log out and back in, so the docker group applies

/srv/marinnex/Marinnex/deploy/scripts/deploy.sh
```

`setup-server.sh` creates the swap file, installs Docker and the AWS CLI, turns
on unattended security upgrades, creates `/srv/marinnex/data` owned by uid
10001 (the non-root user inside the image), and schedules the nightly file
backup.

---

## Every release after that

```bash
/srv/marinnex/Marinnex/deploy/scripts/deploy.sh
```

It pulls both repositories, checks the toolkit out at **`v0.9.0`** — pinned,
because this release depends on that version and a deployment that silently
picked up newer toolkit code would be a different system from the one that was
tested — fetches secrets, builds, runs migrations in a **one-off container**,
starts everything, and polls `/v1/health` for five minutes. It exits non-zero
and prints the last 40 log lines if the service never becomes healthy.

Migrations run in their own container deliberately: running them from the API's
start command would race two uvicorn workers against each other on one SQLite
file.

---

## Inviting people

Registration is closed in production (`FDIP_ALLOW_REGISTRATION=false`), so
`/auth/register` answers 403 with a message, and the UI hides the sign-up link
and says "invite only" instead of leaving someone to guess.

```bash
/srv/marinnex/Marinnex/deploy/scripts/create-user.sh someone@example.com
```

It generates a 24-character temporary password and prints it **once**. Pass it
on directly and ask them to change it. It is never mailed or logged.

When someone locks themselves out — there is no reset email to fall back on:

```bash
/srv/marinnex/Marinnex/deploy/scripts/reset-password.sh someone@example.com
```

It changes the stored hash and touches nothing else; the account, its project
and its documents are the same afterwards.

---

## Backups

Two different things, because they fail differently.

**The database** is replicated continuously by Litestream to
`s3://$BACKUP_BUCKET/litestream/fdip.db`: a snapshot a day, WAL frames in
between, seven days of retention.

**The uploaded files** are synced nightly at 03:15 UTC by `backup-files.sh` to
`s3://$BACKUP_BUCKET/files/`. Restoring the database without the files gives
you a catalogue of documents nobody can open.

### Prove it

```bash
BACKUP_BUCKET=marinnex-backups /srv/marinnex/Marinnex/deploy/scripts/restore-test.sh
```

Restores the latest copy into a temporary folder, runs SQLite's own
`integrity_check`, and prints row counts. It warns if the restored database is
empty — that proves the pipe works, not that the data is there. **A backup
nobody has restored is a hypothesis.** Run it after the first real documents
arrive, and periodically after that.

---

## What production changes

| Setting | Development | Production |
|---|---|---|
| `FDIP_ENV` | `development` | `production` |
| Provider | `mock` is fine | `mock` is **refused at startup**; use `live`, or `recorded` for a demo |
| `FDIP_KEY_PEPPER` | required | required |
| `FDIP_SESSION_SECRET` | generated if absent | **required** |
| `DEEPSEEK_API_KEY` | optional | **required** |
| `FDIP_AI_MONTHLY_CEILING_USD` | defaults to 20 | **required** |
| Registration | open | closed |
| Cookies | `Secure` only over HTTPS | `Secure`, `HttpOnly`, `SameSite=Lax` |

Each of those refusals happens **at startup**, not at the first request. A
server that starts without a pepper and quietly invalidates every API key is
worse than one that will not start.

---

## Security at the edge

The Caddyfile sets HSTS for a year, `X-Content-Type-Options: nosniff`,
`X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`,
and a CSP that allows only this origin plus `data:`/`blob:` images — the page
images the review screen draws. No inline script and no CDN: everything the app
needs is in the bundle.

Bodies over **20 MB** are refused at the edge, matching the application's own
upload limit, so a larger one is never buffered by the API. Verified: a 21 MB
upload is cut off. Note the client sees a **connection reset, not a clean
413** — Caddy stops reading rather than replying. Anything that does reach the
API gets a proper `file_too_large` problem document.

Access logs are JSON with the **query string stripped**, because a query can
carry a document id or an idempotency key.

Rate limits are in-process, per calling address: 10 login attempts a minute and
30 uploads or extractions. Caddy passes `X-Forwarded-For`; without it every
request would appear to come from the container network and one address could
exhaust the limit for everyone. Being in-process is honest for one server and
wrong for two — see `CLAUDE.md` §8.1 on not building Redis yet.

---

## Testing it locally

Docker Desktop, from the parent of this repository:

```bash
cd ..                                  # the folder holding Marinnex and Toolkits_Management
cp Marinnex/.env.example .env          # set DOMAIN=localhost and a pepper
docker compose -f Marinnex/deploy/docker-compose.prod.yml --env-file .env up --build -d
```

Caddy issues an internal certificate for `localhost`, so expect a browser
warning. To exercise the stack without a provider key, override the mode for
that run only — production normally forbids it:

```bash
FDIP_ENV=development FDIP_PROVIDER_MODE=mock \
  docker compose -f Marinnex/deploy/docker-compose.prod.yml --env-file .env up --build -d
```

---

## When something is wrong

| Symptom | Where to look |
|---|---|
| Deploy says it never became healthy | `docker compose … logs api --tail 100` |
| No certificate | DNS A record, and ports 80/443 open; `docker compose … logs caddy` |
| Documents stay `processing` | the worker is down: `docker compose … ps` |
| `/v1/health` shows a large `worker_heartbeat_age_seconds` | the same |
| Server will not start | it will say which variable is missing; that is the design |
| "Failed to fetch" on sign-in, nothing in the server log | The bundle was built with the development API base, so the browser called `localhost:8000` and the CSP blocked it before the request left. `Dockerfile.web` now fails the build if `localhost:8000` appears in `dist/`. Rebuild the web image. |
| Out of memory | `free -h`; check the swap file exists and `vm.swappiness` is 10 |
