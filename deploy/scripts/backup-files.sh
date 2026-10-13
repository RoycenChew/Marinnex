#!/usr/bin/env bash
# Nightly sync of the uploaded documents to S3.
#
# Litestream replicates the database continuously; it does not know about the
# files the database points at. Restoring one without the other gives you a
# catalogue of documents nobody can open.
set -euo pipefail

SOURCE="${FILES_DIR:-/srv/marinnex/data/blobs}"
BUCKET="${BACKUP_BUCKET:?set BACKUP_BUCKET}"
REGION="${AWS_REGION:-ap-southeast-5}"

if [ ! -d "$SOURCE" ]; then
    echo "backup-files: ${SOURCE} does not exist" >&2
    exit 1
fi

# No --delete: a file removed locally by mistake should still be recoverable.
# Content-addressed blobs are never rewritten, so the sync only ever adds.
aws s3 sync "$SOURCE" "s3://${BUCKET}/files/" \
    --region "$REGION" \
    --only-show-errors

echo "backup-files: synced $(find "$SOURCE" -type f | wc -l) files to s3://${BUCKET}/files/"
