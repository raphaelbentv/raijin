# Raijin incident runbook

## First checks

```bash
curl -fsS "$API_URL/health"
curl -fsS "$API_URL/health/full" | jq
curl -fsS "$API_URL/metrics/prometheus" | head -50
docker compose ps
docker compose logs --tail=200 backend worker beat
```

If `/health` fails, treat the API as unavailable. If `/health/full` is degraded, use the dependency name to route the incident.

## OCR broken

Signals:

- `raijin_invoices_total{status="failed"}` rising
- `raijin_ocr_success_ratio` dropping
- worker logs contain `azure_error`, `rate_limited`, or `azure_di_not_configured`

Actions:

1. Check Azure Document Intelligence availability and quota.
2. Verify `AZURE_DI_ENDPOINT`, `AZURE_DI_KEY`, `AZURE_DI_MODEL`, and `AZURE_DI_LOCALE`.
3. Restart only the worker after fixing secrets:

```bash
docker compose restart worker
```

4. Requeue failed invoices only after confirming the connector is healthy.

## Worker stuck

Signals:

- `/health/full` reports `worker` down
- invoices stay in `processing`
- Redis is healthy but Celery has no active consumers

Actions:

```bash
docker compose logs --tail=200 worker
docker compose restart worker beat
docker compose exec redis redis-cli -n 1 LLEN celery
```

If the queue grows after restart, scale workers:

```bash
docker compose up -d --scale worker=3
```

## Azure outage

Signals:

- Azure status page incident
- multiple tenants affected
- transient errors in worker logs

Actions:

1. Pause new OCR processing if error volume is high by stopping workers.
2. Keep API and upload path online so invoices remain stored.
3. Restart workers when Azure recovers.
4. Run a small upload validation before reopening normal processing.

## Database degraded

Signals:

- `/health/full` reports `postgres` down
- backend logs include connection pool timeouts
- high API latency across all endpoints

Actions:

1. Check managed Postgres status and connection limits.
2. Restart backend only after the database is available.
3. Restore from the newest verified backup if corruption or data loss is confirmed.

## Object storage degraded

Signals:

- uploads fail
- PDF previews fail
- `/health/full` reports `object_storage` down

Actions:

1. Check bucket existence, region, credentials, and endpoint.
2. Validate with:

```bash
aws s3 ls "s3://$S3_BUCKET_INVOICES" --endpoint-url "$S3_ENDPOINT_URL"
```

3. If data is missing, sync from `OBJECT_BACKUP_URI`.
