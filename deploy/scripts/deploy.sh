#!/usr/bin/env bash
# Pull, build, migrate, start, and refuse to claim success until the service
# answers. Safe to re-run: every step is idempotent.
set -euo pipefail

ROOT="${MARINNEX_ROOT:-/srv/marinnex}"
APP="$ROOT/Marinnex"
TOOLKIT="$ROOT/Toolkits_Management"
TOOLKIT_TAG="${TOOLKIT_TAG:-v0.9.0}"
COMPOSE=(docker compose -f "$APP/deploy/docker-compose.prod.yml" --env-file "$ROOT/.env")

echo "==> Updating the application"
git -C "$APP" pull --ff-only

# Pinned, not latest: this release depends on v0.9.0 of the toolkit, and a
# deployment that silently picked up newer toolkit code would be a different
# system from the one that was tested.
echo "==> Updating the toolkit to ${TOOLKIT_TAG}"
git -C "$TOOLKIT" fetch --tags --quiet
git -C "$TOOLKIT" checkout --quiet "$TOOLKIT_TAG"

echo "==> Fetching secrets"
"$APP/deploy/scripts/fetch-secrets.sh"

echo "==> Building images"
cd "$ROOT"
"${COMPOSE[@]}" build

# A one-off container, before anything serves traffic. Running migrations from
# inside the API's start command would race the two uvicorn workers against
# each other on the same SQLite file.
echo "==> Running database migrations"
"${COMPOSE[@]}" run --rm --no-deps api python -m alembic upgrade head

echo "==> Starting services"
"${COMPOSE[@]}" up -d --remove-orphans

echo "==> Waiting for health"
for attempt in $(seq 1 60); do
    if curl -fsS --max-time 5 http://localhost/v1/health >/dev/null 2>&1; then
        echo "==> Healthy after ${attempt} attempt(s)"
        "${COMPOSE[@]}" ps
        exit 0
    fi
    sleep 5
done

echo "deploy: service did not become healthy in five minutes" >&2
"${COMPOSE[@]}" ps >&2
# The last lines of each log, so the failure is visible without a second
# round trip to the server.
"${COMPOSE[@]}" logs --tail 40 >&2
exit 1
