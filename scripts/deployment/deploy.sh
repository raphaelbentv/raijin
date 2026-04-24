#!/usr/bin/env bash
set -euo pipefail

# Déploiement production Raijin
# Usage : ./scripts/deployment/deploy.sh [staging|production]

ENVIRONMENT="${1:-staging}"
COMPOSE_FILE="docker-compose.prod.yml"

if [ ! -f ".env.production" ]; then
    echo "ERROR: .env.production is missing. Copy .env.production.example and fill in."
    exit 1
fi

echo "▶ Pulling latest code…"
git pull --ff-only

echo "▶ Building images ($ENVIRONMENT)…"
docker compose -f "$COMPOSE_FILE" build

echo "▶ Applying DB migrations…"
docker compose -f "$COMPOSE_FILE" run --rm backend alembic upgrade head

echo "▶ Rolling restart…"
docker compose -f "$COMPOSE_FILE" up -d --remove-orphans

echo "▶ Health check…"
sleep 5
docker compose -f "$COMPOSE_FILE" ps

echo "✅ Deployment to $ENVIRONMENT complete."
