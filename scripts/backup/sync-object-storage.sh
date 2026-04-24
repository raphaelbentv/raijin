#!/usr/bin/env sh
set -eu

S3_BUCKET_INVOICES="${S3_BUCKET_INVOICES:?S3_BUCKET_INVOICES is required}"
BACKUP_URI="${OBJECT_BACKUP_URI:?OBJECT_BACKUP_URI is required, for example s3://raijin-backups/invoices}"
S3_ENDPOINT_URL="${S3_ENDPOINT_URL:-}"

AWS_ARGS=""
if [ -n "$S3_ENDPOINT_URL" ]; then
  AWS_ARGS="--endpoint-url $S3_ENDPOINT_URL"
fi

aws $AWS_ARGS s3 sync "s3://$S3_BUCKET_INVOICES" "$BACKUP_URI" \
  --only-show-errors \
  --delete
