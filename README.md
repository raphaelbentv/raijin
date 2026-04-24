# ⚡ Raijin — Invoice Automation Layer

Automatisation OCR de factures fournisseurs avec validation humaine et export comptable.

**État** : MVP 30 jours complet (4 sprints livrés).
**Docs** : [guide utilisateur FR](docs/user-guide/fr.md) · [user guide EN](docs/user-guide/en.md) · [ADRs](docs/adr/) · [déploiement](docs/architecture/deployment.md)

## Stack

- **Frontend** — Next.js 14 + TypeScript + Tailwind + shadcn/ui
- **Backend API** — Python 3.12 + FastAPI + SQLAlchemy async
- **Workers** — Celery + Redis
- **DB** — PostgreSQL 16
- **Storage** — MinIO (dev) / S3 (prod)
- **OCR** — Azure Document Intelligence (`prebuilt-invoice`)

## Quick start

```bash
cp .env.example .env
make up          # Démarre postgres, redis, minio, backend, worker, frontend
make migrate     # Applique les migrations Alembic
make logs        # Suit les logs
```

Services :

| Service       | URL                         |
|---------------|-----------------------------|
| Frontend      | http://localhost:6100       |
| Backend       | http://localhost:6200       |
| API docs      | http://localhost:6200/docs  |
| MinIO API     | http://localhost:6900       |
| MinIO console | http://localhost:6901       |
| Postgres      | localhost:6432              |
| Redis         | localhost:6379              |

## Structure

```
Raijin/
├── backend/        # API FastAPI
├── frontend/       # App Next.js
├── workers/        # Workers Celery (OCR, validation)
├── shared/         # Schémas partagés
├── infrastructure/ # Configs Docker, déploiement
├── scripts/        # Outils (ocr-test, deployment)
└── docs/           # ADR, architecture, guides
```

## Commandes

```bash
make up            # Lance l'ensemble de la stack
make down          # Stoppe tout
make logs          # Suit les logs agrégés
make logs-backend  # Logs backend uniquement
make migrate       # Applique les migrations DB
make migration m="add column foo"  # Crée une migration
make test          # Lance la suite de tests
make lint          # Ruff + eslint
make format        # Ruff format + prettier
make shell-backend # Shell dans le container backend
make psql          # Accès psql
```

## Déploiement

Voir [docs/architecture/deployment.md](docs/architecture/deployment.md) pour le runbook complet staging/production.

Quick start staging :
```bash
cp .env.production.example .env.production  # puis remplir
./scripts/deployment/deploy.sh staging
```

## Endpoints principaux

| Endpoint | Description |
|----------|-------------|
| `POST /auth/register` | Créer compte + tenant |
| `POST /auth/login` | Login JWT |
| `POST /invoices/upload` | Upload facture (PDF/JPG/PNG ≤ 20 Mo) |
| `GET /invoices` | Lister factures du tenant (filtres statut, pagination) |
| `GET /invoices/stats` | Compteurs par statut |
| `GET /invoices/:id` | Détail + URL signée + lignes + supplier |
| `PATCH /invoices/:id` | Éditer champs (en `ready_for_review` ou `rejected`) |
| `POST /invoices/:id/confirm` | Valider (HTTP 422 si erreurs) |
| `POST /invoices/:id/reject` | Rejeter avec raison |
| `POST /invoices/:id/skip` | Remettre à plus tard |
| `POST /invoices/:id/reopen` | Réouvrir une facture validée/rejetée |
| `GET /invoices/:id/corrections` | Historique des corrections |
| `GET /exports/excel` | Export .xlsx filtrable (from, to, supplier_id, status_filter) |
| `GET /metrics` | Snapshot métriques tenant (succès OCR, confidence, corrections) |
| `GET /health`, `/health/db`, `/health/worker` | Probes |

## Statuts d'une facture

`uploaded → processing → ready_for_review → confirmed`
avec `rejected` / `failed` comme branches, et `reopen` pour rebasculer. Matrice complète : [ADR 0002](docs/adr/0002-invoice-status-transitions.md).
