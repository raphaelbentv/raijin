# Raijin — Checklist production

Cette checklist couvre le go-live d'un pilote client. Elle est pensée pour un déploiement en staging puis prod, avec un seul tenant actif.

---

## 1. Prérequis infrastructure

### VPS ou App Service
- [ ] Ubuntu 22.04+ (ou Debian 12) — 4 GB RAM min, 2 vCPU, 40 GB SSD
- [ ] Docker 24+ et docker compose v2 installés
- [ ] Utilisateur non-root `deploy` avec accès sudo limité
- [ ] Firewall ufw : autoriser 22 (ssh restreint IP), 80, 443 ; bloquer le reste
- [ ] fail2ban configuré sur ssh

### DNS
- [ ] `app.<domaine>` → A record vers VPS
- [ ] `api.<domaine>` → A record vers VPS
- [ ] TTL 300s pour pouvoir bouger rapidement en cas d'incident

### TLS (Let's Encrypt via certbot)
- [ ] Certificats générés pour `app.` et `api.`
- [ ] Renouvellement automatique (`systemctl status certbot.timer`)
- [ ] Certificats copiés dans `infrastructure/docker/certs/`

---

## 2. Secrets

- [ ] `./scripts/deployment/generate-secrets.sh` exécuté
- [ ] `ENCRYPTION_KEY` stocké dans gestionnaire de secrets (1Password, Azure Key Vault…)
- [ ] `JWT_SECRET` stocké idem
- [ ] `POSTGRES_PASSWORD` stocké idem
- [ ] `.env.production` copié sur le VPS avec `chmod 600`, propriétaire `deploy:deploy`
- [ ] `.env.production` **absent du git** (vérifier `.gitignore`)
- [ ] Plan de rotation documenté : quand et comment renouveler chaque secret

---

## 3. Services externes

### Azure Document Intelligence
- [ ] Ressource créée en région UE (West Europe recommandé)
- [ ] Niveau S0 pour prod (pas F0 qui est limité)
- [ ] Clé copiée dans `AZURE_DI_KEY`
- [ ] Test : `docker compose exec backend python -m app.scripts.smoke_connectors`

### Azure AD App (pour Outlook)
- [ ] App registration créée
- [ ] Redirect URI production : `https://api.<domaine>/integrations/outlook/callback`
- [ ] API permissions : `Mail.Read`, `offline_access`, `User.Read` (delegated)
- [ ] Client secret créé, copié dans `MICROSOFT_CLIENT_SECRET`

### Google Cloud (pour Gmail + Drive)
- [ ] Projet GCP créé
- [ ] OAuth 2.0 Client ID "Web application"
- [ ] Redirect URI : `https://api.<domaine>/integrations/google/callback`
- [ ] Scopes activés : `gmail.readonly`, `drive.readonly`
- [ ] Screen de consentement en production (demande de verification si > 100 users)

### myDATA (AADE)
- [ ] Choix fait : connecteur certifié (Epsilon Digital / SoftOne) OU AADE direct
- [ ] Si direct : compte AADE dev créé pour tests sur `mydataapidev.aade.gr`
- [ ] Si direct prod : `aade-user-id` + `Ocp-Apim-Subscription-Key` obtenus
- [ ] Si connecteur tiers : contrat signé + credentials API reçus
- [ ] XML schema v1.0.x validé (version actuelle de l'AADE)

### ERP (SoftOne / Epsilon Net)
- [ ] Credentials de test obtenus
- [ ] Série de facturation configurée dans l'ERP
- [ ] Mapping TVA validé (codes 24/13/6/0 → ratios)
- [ ] `erp_connector.config` ajusté selon le client (company, branch, form name…)

---

## 4. Base de données

- [ ] Postgres managé recommandé (Azure DB for PG, AWS RDS, Scaleway) — pas du containerisé en prod
- [ ] Connection string avec `sslmode=require` en prod
- [ ] Backup quotidien configuré (`pg_dump` → S3/Blob UE)
- [ ] Rétention 30 jours min, test de restauration fait au moins une fois
- [ ] Monitoring : alerte si disque < 20% libre
- [ ] Migrations Alembic appliquées : `docker compose -f docker-compose.prod.yml exec backend alembic upgrade head`

---

## 5. Observabilité

### Logs
- [ ] `LOG_LEVEL=INFO` en prod (pas DEBUG)
- [ ] Logs structurés JSON (automatique si `ENVIRONMENT=production`)
- [ ] Shipper configuré (Loki / Datadog / Papertrail / Better Stack)
- [ ] Rotation log docker limitée : `log-opts max-size=50m max-file=3` dans daemon.json

### Métriques
- [ ] Endpoint `/metrics` accessible (admin only)
- [ ] Endpoint `/metrics/prometheus` scrapé par Prometheus
- [ ] Endpoint `/health`, `/health/db`, `/health/worker`, `/health/full` testés
- [ ] Dashboard Grafana `Raijin production overview` provisionné
- [ ] Sentry configuré : `SENTRY_DSN`, `NEXT_PUBLIC_SENTRY_DSN`, `RELEASE_VERSION`

### Alertes
- [ ] Backend down > 2 min
- [ ] `/health/full` status `down` > 2 min
- [ ] `/health/worker` degraded > 5 min
- [ ] OCR success rate < 85% sur 1h
- [ ] Disk usage Postgres < 20%
- [ ] Certbot expiration < 14 jours

---

## 6. Sécurité

- [ ] `CORS_ORIGINS` strict : uniquement le domaine front de prod (pas de `*`)
- [ ] `JWT_ACCESS_TTL_MINUTES=15` en prod (30 en dev OK)
- [ ] `ENVIRONMENT=production` → active HSTS et les security headers
- [ ] Rate limit sur `/auth/login` (10/min) et `/auth/register` (3/min) actifs
- [ ] Pas de `0.0.0.0:5432/6379/9000` exposé publiquement (vérifier `docker ps`)
- [ ] Scan OWASP ZAP passé une fois avant go-live
- [ ] RGPD : DPA signé avec le client ; politique de rétention des factures documentée

---

## 7. Déploiement initial

```bash
ssh deploy@vps
git clone git@github.com:<org>/Raijin.git /opt/raijin
cd /opt/raijin

# 1. Secrets
./scripts/deployment/generate-secrets.sh
cat .env.production.example .env.production.secrets > .env.production
vim .env.production    # remplir URLs, clés API
chmod 600 .env.production
rm .env.production.secrets

# 2. TLS
sudo certbot certonly --webroot -w /var/www/certbot \
    -d app.raijin.example.com -d api.raijin.example.com
sudo cp /etc/letsencrypt/live/api.raijin.example.com/{fullchain,privkey}.pem \
    infrastructure/docker/certs/

# 3. Stack
./scripts/deployment/deploy.sh production

# 4. Smoke test
docker compose -f docker-compose.prod.yml exec backend \
    python -m app.scripts.smoke_connectors
curl -fsS https://api.raijin.example.com/health/full
curl -fsS https://api.raijin.example.com/metrics/prometheus | head

# 5. Créer le premier admin client via /auth/register (depuis le front)
```

---

## 8. Pilote client

- [ ] Onboarding : admin client créé, compte reviewer pour l'équipe compta
- [ ] Documentation user envoyée : `docs/user-guide/fr.md` (+ `en.md` si besoin)
- [ ] Dossier test Azure DI : 10-20 factures réelles du client, script `scripts/ocr-test/` lancé
- [ ] Verdict go/no-go OCR : confidence moyenne ≥ 0.90
- [ ] Si no-go : voir ADR 0001 — Plan B (Google DocAI / Mindee / custom model)

---

## 9. Matrice environnements

| | dev | staging | prod |
|---|---|---|---|
| ENVIRONMENT | development | production | production |
| LOG_LEVEL | DEBUG | INFO | INFO |
| JWT_ACCESS_TTL_MINUTES | 30 | 15 | 15 |
| CORS_ORIGINS | localhost:6100 | staging.app | app.prod |
| Postgres | containerisé | managé | managé |
| MinIO/S3 | MinIO local | Azure Blob UE | Azure Blob UE |
| Azure DI | F0 test | S0 test | S0 prod |
| Backups | ❌ | nightly | nightly + offsite |
| Monitoring | logs only | + metrics | + alerting |
| TLS | non | Let's Encrypt | Let's Encrypt + HSTS |

---

## 10. Rollback plan

En cas d'incident :

```bash
# 1. Retour au tag précédent
git checkout <previous-tag>
docker compose -f docker-compose.prod.yml up -d --build

# 2. Si la migration DB casse :
docker compose -f docker-compose.prod.yml exec backend alembic downgrade -1

# 3. Restauration DB depuis backup :
gunzip < /backups/raijin-YYYYMMDD.sql.gz | \
    docker compose -f docker-compose.prod.yml exec -T postgres \
    psql -U raijin_prod raijin
```

Temps cible : **RTO 30 min**, **RPO 24h** (backup quotidien).

Voir aussi :

- `docs/STAGING.md` pour le déploiement staging et la checklist pre-pilot
- `docs/RUNBOOK.md` pour OCR cassé, worker stuck, outage Azure, DB et object storage
- `scripts/backup/README.md` pour les jobs de backup Postgres + object storage
- `scripts/load-test/README.md` pour le scénario k6 100 factures/min

---

## 11. Points ouverts pré-launch

⚠️ Les stubs suivants doivent être validés avant go-live avec données réelles :

- [ ] **Epsilon Digital** (myDATA connector) — URLs exactes à confirmer avec doc éditeur
- [ ] **SoftOne myDATA** (myDATA connector) — URLs exactes à confirmer
- [ ] **SoftOne ERP** (`/s1services`) — confirmer la série FINDOC (souvent 3000 pour achats)
- [ ] **Epsilon Net** (`/api/v1/documents`) — confirmer le schéma et le type `PURCHASE_INVOICE`

Chaque validation = modifier le fichier de connector concerné + retester en staging.
