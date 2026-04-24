# Raijin — Staging runbook

Staging est l'environnement pré-pilote pour Sprint 9. Il tourne sur les mêmes images et configs que production, avec `ENVIRONMENT=staging` et des secrets non-production.

## État au 2026-04-24

Tout ce qui peut être préparé en local **l'est déjà** :

- ✅ `scripts/deployment/deploy.sh` supporte `staging` et `production`
- ✅ `scripts/deployment/generate-secrets.sh` génère `ENCRYPTION_KEY` (Fernet), `JWT_SECRET`, `POSTGRES_PASSWORD`, `S3_SECRET_KEY`
- ✅ `.env.staging.example` liste toutes les variables nécessaires
- ✅ `.env.staging` local bootstrappé avec les 4 secrets crypto (gitignored)
- ✅ `docker-compose.prod.yml` validé syntaxiquement avec `--env-file .env.staging`
- ✅ Artefacts monitoring : `infrastructure/monitoring/prometheus.yml`, Grafana dashboard provisionné
- ✅ Artefacts backup : `scripts/backup/backup-postgres.sh`, `sync-object-storage.sh`
- ✅ k6 load test : `scripts/load-test/k6-upload-100.js`

## Ce qu'il reste à fournir (bloquants externes)

| Variable | Source | Notes |
|---|---|---|
| Provider cloud | Railway / Fly.io / DigitalOcean App Platform / VPS | À décider |
| Domaine staging | ex. `staging-raijin.com` | DNS A record → IP provider |
| TLS cert | Let's Encrypt via nginx ou provider | Automatique sur Railway/Fly.io |
| `AZURE_DI_ENDPOINT` + `AZURE_DI_KEY` | [Azure portal](https://portal.azure.com) → Document Intelligence en région UE | Compte Azure requis |
| `S3_ENDPOINT_URL`, `S3_ACCESS_KEY`, `S3_BUCKET_INVOICES` | AWS S3 **ou** DO Spaces **ou** Cloudflare R2 **ou** MinIO managé | Préférer région UE |
| `SMTP_HOST` / `SMTP_USERNAME` / `SMTP_PASSWORD` **ou** `RESEND_API_KEY` | Resend.com (simple) ou SES / Mailjet / Sendgrid | Resend recommandé pour commencer |
| `SENTRY_DSN` + `NEXT_PUBLIC_SENTRY_DSN` | [sentry.io](https://sentry.io) → créer projet Python + Next.js | Optionnel mais recommandé |
| `GRAFANA_ADMIN_PASSWORD` | Choisir un mot de passe fort | Accès dashboard monitoring |

## Déployer

Une fois les secrets externes obtenus :

1. Compléter `.env.staging` avec les valeurs fournies par le provider
2. Pousser le dépôt sur le provider (ou configurer un déploiement `git push` avec `docker-compose.prod.yml`)
3. Exécuter :

```bash
./scripts/deployment/deploy.sh staging
```

Le script :
- pull le dernier code
- build les images
- applique les migrations Alembic (`alembic upgrade head`)
- lance les services en rolling restart
- attend le `/health` backend

4. Vérifier la disponibilité :

```bash
curl -fsS https://staging-raijin.com/api/health
curl -fsS https://staging-raijin.com/api/health/full
curl -fsS https://staging-raijin.com/api/metrics/prometheus | head
```

## Monitoring

Prometheus scrape `backend:8000/metrics/prometheus`.
Grafana est provisionné avec le dashboard `Raijin production overview` et la datasource Prometheus.

Pour le monitoring local :

```bash
docker compose --profile monitoring up -d prometheus grafana
```

Puis ouvrir Grafana sur `http://localhost:6300`.

## Release checklist

- [ ] `RELEASE_VERSION` est mis au SHA de commit ou au tag de release
- [ ] `SENTRY_DSN` et `NEXT_PUBLIC_SENTRY_DSN` sont renseignés
- [ ] `NEXT_PUBLIC_API_URL` pointe vers l'URL publique staging API
- [ ] `/health/full` retourne `ok` (ou un `degraded` documenté)
- [ ] Les jobs de backup (pg_dump + sync object storage) sont cron schedulés
- [ ] Le scénario k6 `k6-upload-100.js` passe avant d'ouvrir aux pilotes
- [ ] Admin Grafana protégé par mot de passe fort
- [ ] DNS A record pointe vers le provider
- [ ] TLS cert Let's Encrypt actif

## Rollback

```bash
# Revenir à l'avant-dernière image
git revert <sha>
./scripts/deployment/deploy.sh staging

# Ou restore DB depuis un backup
scripts/backup/restore-postgres.sh <backup_file>
```
