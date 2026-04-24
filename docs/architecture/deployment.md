# Déploiement — Staging & Production

## Architecture cible (staging MVP)

```
                     ┌──────────┐
                     │  Nginx   │  TLS termination (Let's Encrypt)
                     │  :443    │
                     └────┬─────┘
            ┌─────────────┴─────────────┐
            ▼                           ▼
     ┌──────────┐                 ┌──────────┐
     │ Frontend │ :3000           │ Backend  │ :8000 (2 workers uvicorn)
     └──────────┘                 └────┬─────┘
                                       │
                              ┌────────┼────────┐
                              ▼        ▼        ▼
                       ┌──────────┐ ┌──────┐ ┌──────┐
                       │ Postgres │ │Redis │ │  S3  │
                       └──────────┘ └──────┘ └──────┘
                                       ▲
                                       │
                                  ┌────┴────┐
                                  │ Worker  │  Celery, 4 concurrency, max 100 tasks/child
                                  └─────────┘
```

Tout est sur un VPS unique en staging MVP. Prod recommandée :
- Postgres managé (Azure Database for PostgreSQL / AWS RDS / Scaleway)
- Redis managé
- S3 = Azure Blob Storage (région UE)
- Backend + worker + frontend en Docker sur VPS ou App Service / ECS

## Prérequis VPS

- Ubuntu 22.04+ (ou debian 12+)
- Docker 24+ et docker compose v2
- 4 Go RAM min (2 pour Postgres + 2 pour apps), 2 vCPU, 40 Go SSD
- DNS configuré : `app.<domain>` + `api.<domain>` pointent vers le VPS

## Première installation

```bash
# Sur le VPS
ssh deploy@<vps-ip>
git clone git@github.com:<org>/Raijin.git /opt/raijin
cd /opt/raijin
cp .env.production.example .env.production
vim .env.production           # remplir toutes les valeurs

# Générer JWT_SECRET
python3 -c "import secrets; print(secrets.token_urlsafe(64))"

# TLS via certbot (une seule fois)
sudo certbot certonly --webroot -w /var/www/certbot \
    -d app.raijin.example.com -d api.raijin.example.com

# Copier les certs dans infrastructure/docker/certs/
sudo cp /etc/letsencrypt/live/api.raijin.example.com/fullchain.pem infrastructure/docker/certs/
sudo cp /etc/letsencrypt/live/api.raijin.example.com/privkey.pem infrastructure/docker/certs/

# Premier déploiement
./scripts/deployment/deploy.sh staging
```

## Déploiements suivants

```bash
cd /opt/raijin
./scripts/deployment/deploy.sh staging
```

Le script fait :
1. `git pull`
2. `docker compose build`
3. `alembic upgrade head` (migrations)
4. Rolling restart des services
5. Health check

## Rollback

```bash
git checkout <previous-tag>
docker compose -f docker-compose.prod.yml up -d --build
# Si la migration doit être reculée :
docker compose -f docker-compose.prod.yml exec backend alembic downgrade -1
```

## Monitoring de base

### Logs agrégés

```bash
docker compose -f docker-compose.prod.yml logs -f backend worker
```

Les logs structurés (JSON en prod via `structlog`) peuvent être shippés vers :
- Loki (recommandé, simple Grafana stack)
- Datadog Agent
- Papertrail / Better Stack

### Healthchecks

- `GET /health` — liveness API
- `GET /health/db` — Postgres up
- `GET /health/worker` — Celery répond (ping)
- `GET /metrics` — compteurs factures + OCR success rate + confidence moyenne

### Alertes minimales à configurer

| Alerte | Seuil | Action |
|--------|-------|--------|
| Backend down | HTTP 5xx > 5% sur 5 min | Page oncall |
| Worker down | `/health/worker` degraded > 5 min | Page oncall |
| OCR success rate | < 85% sur 1h | Investigation Azure DI |
| Postgres disk | < 20% libre | Augmenter volume |
| Certbot expiration | < 14 jours | Renouvellement auto ou manuel |

## Backup

### Postgres

Backup quotidien du volume `postgres_data` via `pg_dump` :

```bash
# Dans un cron
docker compose -f docker-compose.prod.yml exec -T postgres \
    pg_dump -U raijin_prod raijin | gzip > /backups/raijin-$(date +%Y%m%d).sql.gz
```

Rétention 30 jours recommandée. Upload vers S3/Azure Blob différent de la production.

### Fichiers factures (S3)

Azure Blob avec versioning + soft delete (30 jours) activé. Pas de backup supplémentaire nécessaire.

## Rotation des secrets

- `JWT_SECRET` : rotation annuelle. Tous les utilisateurs devront se reconnecter.
- `AZURE_DI_KEY` : rotation trimestrielle via portail Azure.
- `S3_SECRET_KEY` : rotation trimestrielle.

## Runbook incidents

### Backend crash loop

```bash
docker compose -f docker-compose.prod.yml logs backend --tail 100
# Si c'est une migration qui crashe :
docker compose -f docker-compose.prod.yml exec backend alembic current
docker compose -f docker-compose.prod.yml exec backend alembic downgrade -1
```

### Worker bloqué

```bash
# Purger la queue
docker compose -f docker-compose.prod.yml exec redis redis-cli FLUSHDB
# Reprocess manuel d'une facture
docker compose -f docker-compose.prod.yml exec backend python -c "
from app.core.celery_client import enqueue_invoice_ocr
enqueue_invoice_ocr('<invoice-uuid>')
"
```

### Taux d'échec OCR élevé

1. Vérifier `/health/worker` — si degraded, problème Celery/Redis
2. Vérifier le portail Azure DI pour incidents / quota
3. Regarder `validation_errors` sur un échantillon de factures échouées
4. Si systémique, voir ADR 0001 — Plan B Google DocAI / Mindee
