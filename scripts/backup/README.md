# Raijin backups

Automated backup has two jobs:

- Postgres: `backup-postgres.sh` creates a compressed custom-format `pg_dump`.
- Object storage: `sync-object-storage.sh` mirrors the invoice bucket to another S3-compatible bucket.

Example staging cron:

```cron
15 2 * * * cd /srv/raijin && DATABASE_URL="$DATABASE_URL" BACKUP_DIR=/var/backups/raijin/postgres scripts/backup/backup-postgres.sh
35 2 * * * cd /srv/raijin && OBJECT_BACKUP_URI=s3://raijin-staging-backups/invoices scripts/backup/sync-object-storage.sh
```

Restore drill:

```bash
gunzip -c /var/backups/raijin/postgres/raijin-postgres-YYYYMMDDTHHMMSSZ.dump.gz > /tmp/raijin.dump
pg_restore --clean --if-exists --no-owner --dbname "$DATABASE_URL" /tmp/raijin.dump
```

For MinIO staging, set `S3_ENDPOINT_URL`, `AWS_ACCESS_KEY_ID`, and `AWS_SECRET_ACCESS_KEY`.
