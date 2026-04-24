#!/usr/bin/env sh
set -eu

BACKUP_DIR="${BACKUP_DIR:-./backups/postgres}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DATABASE_URL="${DATABASE_URL:?DATABASE_URL is required}"

mkdir -p "$BACKUP_DIR"

OUT="$BACKUP_DIR/raijin-postgres-$TIMESTAMP.dump"
pg_dump "$DATABASE_URL" --format=custom --no-owner --no-privileges --file="$OUT"
gzip -f "$OUT"

find "$BACKUP_DIR" -name "raijin-postgres-*.dump.gz" -mtime +"$RETENTION_DAYS" -delete

echo "$OUT.gz"
