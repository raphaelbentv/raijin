# Raijin staging runbook

Staging is the pre-pilot environment for Sprint 9. It should run the same images and settings as production, with `ENVIRONMENT=staging` and non-production secrets.

## Deploy

1. Copy `.env.staging.example` to the provider secret store.
2. Set managed Postgres, Redis, S3-compatible object storage, Sentry, SMTP/Resend, and Azure Document Intelligence values.
3. Build and start the production compose stack:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.staging up -d --build
```

4. Run migrations:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.staging exec backend alembic upgrade head
```

5. Verify readiness:

```bash
curl -fsS https://staging-raijin.com/api/health
curl -fsS https://staging-raijin.com/api/health/full
curl -fsS https://staging-raijin.com/api/metrics/prometheus | head
```

## Monitoring

Prometheus scrapes `backend:8000/metrics/prometheus`.
Grafana is provisioned with the `Raijin production overview` dashboard and the Prometheus datasource.

For local monitoring:

```bash
docker compose --profile monitoring up -d prometheus grafana
```

Then open Grafana on `http://localhost:6300`.

## Release checklist

- `RELEASE_VERSION` set to the commit SHA or release tag.
- `SENTRY_DSN` and `NEXT_PUBLIC_SENTRY_DSN` set.
- `NEXT_PUBLIC_API_URL` points to the public staging API route.
- `/health/full` returns `ok` or an understood `degraded` state.
- Backup jobs are scheduled for Postgres and object storage.
- k6 upload scenario passes before pilot traffic.
