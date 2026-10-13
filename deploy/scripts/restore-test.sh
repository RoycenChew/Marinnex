#!/usr/bin/env bash
# Prove the backup is restorable. A backup nobody has restored is a hypothesis.
#
# Restores the latest Litestream copy into a temporary folder, runs SQLite's
# own integrity check, and prints row counts for the tables that would matter
# in a real recovery. Touches nothing in production.
set -euo pipefail

BUCKET="${BACKUP_BUCKET:?set BACKUP_BUCKET}"
REGION="${AWS_REGION:-ap-southeast-5}"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

echo "==> Restoring the latest snapshot to ${WORK}"
docker run --rm \
    -e AWS_REGION="$REGION" \
    -v "$WORK:/restore" \
    litestream/litestream:0.5.2 \
    restore -o /restore/fdip.db "s3://${BUCKET}/litestream/fdip.db"

DB="$WORK/fdip.db"
if [ ! -s "$DB" ]; then
    echo "restore-test: nothing was restored" >&2
    exit 1
fi

echo "==> Integrity check"
result="$(sqlite3 "$DB" 'pragma integrity_check;')"
echo "    $result"
if [ "$result" != "ok" ]; then
    echo "restore-test: the restored database is corrupt" >&2
    exit 1
fi

echo "==> Row counts"
for table in users projects documents extractions api_keys audit_events; do
    count="$(sqlite3 "$DB" "select count(*) from ${table};" 2>/dev/null || echo "missing")"
    printf '    %-16s %s\n' "$table" "$count"
done

# An empty database restores cleanly and proves nothing. Say so.
documents="$(sqlite3 "$DB" 'select count(*) from documents;' 2>/dev/null || echo 0)"
if [ "$documents" = "0" ]; then
    echo "restore-test: restored successfully, but it holds no documents —" >&2
    echo "              this proves the pipe works, not that the data is there." >&2
fi

echo "==> Restore test passed"
