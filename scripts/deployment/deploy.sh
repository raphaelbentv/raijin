#!/usr/bin/env bash
set -euo pipefail

# Déploiement Raijin staging / production
# Usage : ./scripts/deployment/deploy.sh [staging|production]

ENVIRONMENT="${1:-staging}"
COMPOSE_FILE="docker-compose.prod.yml"
ENV_FILE=".env.${ENVIRONMENT}"

if [ "$ENVIRONMENT" != "staging" ] && [ "$ENVIRONMENT" != "production" ]; then
    echo "ERROR: environment must be 'staging' or 'production'."
    exit 2
fi

if [ ! -f "$ENV_FILE" ]; then
    echo "ERROR: $ENV_FILE is missing. Copy ${ENV_FILE}.example and fill in the secrets."
    echo "       Run scripts/deployment/generate-secrets.sh to bootstrap JWT_SECRET / ENCRYPTION_KEY / POSTGRES_PASSWORD."
    exit 1
fi

echo "▶ Pulling latest code…"
git pull --ff-only

echo "▶ Building images ($ENVIRONMENT)…"
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" build

echo "▶ Applying DB migrations…"
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" run --rm backend alembic upgrade head

echo "▶ Rolling restart…"
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d --remove-orphans

echo "▶ Waiting for backend health…"
for _ in $(seq 1 30); do
    if docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T backend curl -fsS http://localhost:8000/health >/dev/null 2>&1; then
        echo "  ✓ backend healthy"
        break
    fi
    sleep 2
done

echo "▶ Container status:"
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" ps

echo "✅ Deployment to $ENVIRONMENT complete."
