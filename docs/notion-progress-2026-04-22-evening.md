# 📊 Raijin — Avancées du 22 avril 2026 (soir)

> Update à ajouter à la page Notion ⚡ Raijin (sous-page ou append à "📊 Avancement — 2026-04-22"). Couvre tout ce qui a été livré après la première session (MVP + P2-A→E).

## Résumé

**17 blocs livrés** en une session supplémentaire. La production est désormais déployable.

| Groupe | Blocs | Résumé |
|---|---|---|
| **Phase 2 complétion** | P2-F | Connecteur Epsilon Net (REST JSON) |
| **Refonte design** | D1–D8 | Thème liquid glass dark complet (fonts, sidebar, widgets, toutes pages, seed demo, états vides) |
| **Review page** | R1–R2 | Fix PDF preview (URL MinIO publique) + refonte visuelle |
| **Durcissement prod** | H1–H5 | Secrets, rate limit, CI, smoke tests, PRODUCTION.md |
| **Nav avancée** | N1–N3 | ⌘K command palette, détail fournisseur, notifications center |

## Phase 2 complétée

**P2-F — Epsilon Net ERP** : deuxième implémentation de `ErpConnector` (après SoftOne). API REST JSON moderne, POST `/api/v1/documents` avec payload imbriqué camelCase. Mapper `Invoice → document` dédié. UI `<ErpCard>` active l'option (précédemment désactivée) avec credentials `api_key` + `subscription_id` + `company_id` optionnel. **ADR 0005** rédigée. ⚠️ URLs stubs à valider avec doc éditeur.

## Refonte design liquid glass

- **D1** — Fonts Next.js (Fraunces + Inter + JetBrains Mono via `next/font/google`), globals.css avec blobs ambient violet/indigo/rose + utilities glass réutilisables
- **D2** — Sidebar style "Workly" : 240px, search ⌘K, logo gradient violet, item actif avec glow horizontal, section ADMIN, bloc promo "Connecter myDATA", profil user
- **D3** — 9 widgets dashboard : HeroPending (sparkbars), ConfidenceGauge (jauge radiale SVG), MonthCard, Pipeline OCR, ActivityFeed, TopSuppliers, IntegrationsHealth, TodoList, Shortcuts
- **D4** — Dashboard `/dashboard` remplacé par le grid de widgets + greeting Fraunces italic
- **D5** — États vides élégants : Hero "Bienvenue" si total=0, "Inbox zéro" si pending=0, MonthCard "En attente du premier document", pipeline avec `—`
- **D6** — Script seed demo : `docker compose exec backend python -m app.scripts.seed_demo --reset` crée 5 suppliers, 35 factures variées, corrections, 20 audit logs, 6 notifications
- **D7** — Tout le reste aligné : tokens shadcn passés en dark permanent, `(auth)/layout.tsx` + login/register en glass, `/upload`, `/integrations`, `/admin/users`, `/admin/audit` héritent du dark auto. Fix `use(params)` Next 14
- **D8** — Pages `/invoices` (table complète, filtres pills, pagination) et `/suppliers` (liste avec drapeaux, VAT mono, barre volume) + endpoint backend `GET /suppliers`

## Review page (`/invoices/[id]`)

- **R1** — Fix PDF preview : settings `S3_PUBLIC_URL` + client boto3 dédié au signing. Les URLs passent de `http://minio:9000/…` (interne Docker, inaccessible browser) à `http://localhost:6900/…`
- **R2** — Refonte : header serif italic avec nom fichier, breadcrumb, badge statut, meta inline (fournisseur + OCR %), split 3/2 PDF/form, sections `<Section>` glass (Identité / Montants / Lignes), bannière validation colorée par sévérité, sticky action bar bas avec Save glass + Valider violet + Rejeter rose, `color-scheme: dark` global pour inputs natifs

## Durcissement production

- **H1** — `scripts/deployment/generate-secrets.sh` génère `ENCRYPTION_KEY` Fernet + `JWT_SECRET` 64 chars + `POSTGRES_PASSWORD` + `S3_SECRET_KEY`. `.env.production.example` réécrit avec sections détaillées. `.gitignore` durci
- **H2** — `slowapi` ajouté, **rate limit 10/min sur `/auth/login`** et **3/min sur `/auth/register`** (testé live : 429 après 10 tentatives). `SecurityHeadersMiddleware` injecte `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy` + **HSTS 1 an en prod**
- **H3** — `.github/workflows/ci.yml` : 4 jobs parallèles (backend ruff+pytest, workers idem, frontend typecheck+lint, docker-build gated sur `main` avec cache GHA)
- **H4** — `smoke_connectors.py` CLI : ping postgres / redis / worker / S3 / Azure DI / OAuth Microsoft / OAuth Google / myDATA / ERP. Exit 1 si failure. Utilisable en staging avant release
- **H5** — `docs/PRODUCTION.md` : checklist 11 sections (infra, DNS, TLS, secrets, services externes, DB, observabilité, sécurité, déploiement initial, pilote, matrice env, rollback). 4 points ouverts pré-launch documentés

## Navigation avancée

- **N1** — Command palette **⌘K** : endpoint `GET /search?q=` (factures + fournisseurs), composant `<CommandPaletteProvider>` avec hotkey global, portal modal glass, fuzzy client-side sur navigation + remote search, keyboard nav ↑↓ Enter, groupes "Navigation / Factures / Fournisseurs"
- **N2** — Page `/suppliers/[id]` : header avec drapeau 🇬🇷/🇫🇷/🇩🇪 + VAT mono violet + coordonnées, 4 KPIs (factures, total TTC, moyenne, dernière), tableau factures filtrées via nouvel endpoint `/suppliers/:id/invoices`
- **N3** — Notifications center : nouveau model + migration `20260422_0008`, router `/notifications` (list + mark-read + mark-all), page `/notifications` avec filtres Toutes/Non-lues + icônes par kind + mark on click, **badge live dans la sidebar** (polling 60s, remplace le mock "3")

## Bugs production débloqués

| Bug | Cause | Fix |
|---|---|---|
| `ERR_UNSAFE_PORT` sur 6000 | Chrome bloque port X11 | Backend déplacé sur 6200 |
| passlib/bcrypt ≥5 crash | Incompatibilité au chargement | `bcrypt<5` pinné + rebuild |
| `invalid input value for enum` | SQLAlchemy envoyait nom Python | `values_callable` sur 8 enums |
| `ip_address` pydantic error | IPv4Address vs str | `field_validator` coerce |
| PDF preview "Impossible d'afficher" | URL `minio:9000` interne | `S3_PUBLIC_URL` + signing client dédié |

## ADRs

Nouveau : **ADR 0005 — Intégration Epsilon Net** dans `docs/adr/0005-erp-epsilon-net.md`.

Total ADRs : 5 (OCR retry / transitions Invoice / myDATA connector / SoftOne ERP / Epsilon Net).

## Endpoints nouveaux

```
GET    /search?q=<query>               # ⌘K
GET    /suppliers                      # liste
GET    /suppliers/:id                  # détail
GET    /suppliers/:id/stats            # agrégats
GET    /suppliers/:id/invoices         # factures du fournisseur
GET    /notifications[?unread_only=]   # liste + counts
POST   /notifications/:id/read
POST   /notifications/read-all
```

Plus : `S3_PUBLIC_URL` setting, `RATE_LIMIT_LOGIN_PER_MIN` / `RATE_LIMIT_REGISTER_PER_MIN`.

## Migrations appliquées

| # | Fichier | Contenu |
|---|---|---|
| 0001 | `20260421_0001_initial_schema` | tenants, users, suppliers, invoices, invoice_lines, audit_logs |
| 0002 | `20260421_0002_invoice_corrections` | historique corrections |
| 0003 | `20260421_0003_email_sources` | Outlook/Gmail sources |
| 0004 | `20260421_0004_mydata` | connectors + submissions |
| 0005 | `20260421_0005_erp` | connectors + exports |
| 0006 | `20260421_0006_user_roles_extended` | viewer + reviewer |
| 0007 | `20260422_0007_cloud_drive` | Drive sources |
| 0008 | `20260422_0008_notifications` | notifications |

## Reste à faire avant pilote client

- [ ] Valider URLs Epsilon Digital / SoftOne myDATA avec docs éditeurs
- [ ] Tester `aade_direct` sur `mydataapidev.aade.gr` avec compte dev AADE
- [ ] Configurer Azure AD app (Outlook) + Google Cloud OAuth (Gmail/Drive)
- [ ] Obtenir sample 10-20 factures client → lancer `scripts/ocr-test/` → **go/no-go accuracy**
- [ ] Générer secrets prod via `generate-secrets.sh`
- [ ] Suivre `docs/PRODUCTION.md` pour le go-live

## Stack repo

- **Frontend** : Next.js 14 app router · liquid glass dark · Fraunces + Inter + JetBrains Mono
- **Backend** : FastAPI · SQLAlchemy async · slowapi · structlog · security headers
- **Workers** : Celery + Redis · Azure DI · msal (MS Graph) · httpx (Google OAuth)
- **DB** : Postgres 16 · 8 migrations Alembic
- **Storage** : MinIO dev / S3 prod · signing client dédié
- **CI** : GitHub Actions 4 jobs (backend, workers, frontend, docker)
- **Docs** : 5 ADRs · user guide FR/EN · PRODUCTION.md · deployment runbook

Compte admin test : `raphael@venio.paris` / `RaijinAdmin2026!`.

---

*Écrit automatiquement le 2026-04-22 en fin de session. À coller manuellement dans Notion ⚡ Raijin (MCP Notion déconnecté).*
