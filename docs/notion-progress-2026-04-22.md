# 📊 Raijin — État d'avancement (2026-04-22)

> Update à coller dans la page Notion ⚡ Raijin — Invoice Automation Layer.

## Résumé

**MVP 30 jours + Phase 2 (A→E) livrés en 2 jours**.
Stack tourne en local, compte admin créé, flow register/login validé via navigateur.

- **197 fichiers**, 1,0 Mo
- **8 migrations Alembic** appliquées
- **3 sprints MVP + 5 blocs phase 2** (P2-A Outlook, P2-B myDATA, P2-C SoftOne, P2-D permissions/audit, P2-E Gmail/Drive)

## Ports locaux (après résolution `ERR_UNSAFE_PORT`)

| Service | URL |
|---|---|
| Frontend | http://localhost:6100 |
| Backend API | http://localhost:6200 (changé depuis 6000) |
| API docs | http://localhost:6200/docs |
| MinIO console | http://localhost:6901 |
| Postgres | localhost:6432 |
| Redis | localhost:6380 |

## Compte admin de test

- Email : `raphael@venio.paris`
- Mot de passe : `RaijinAdmin2026!`
- Tenant : Venio

## Sprints livrés

### Sprint 1 — MVP (Fondations + Upload)
Monorepo Docker (backend+workers+frontend+Postgres+Redis+MinIO), auth JWT register/login/refresh/me, upload PDF/JPG/PNG ≤ 20 Mo avec dédoublonnement SHA256, frontend Next.js 14 avec drag&drop, script OCR test isolé Azure DI.

### Sprint 2 — OCR + Extraction
Pipeline Azure Document Intelligence `prebuilt-invoice`, normalizer complet (dates EU/FR/GR, montants 1.234,56 et 1,234.56, VAT EL+FR+DE+IT+ES+BE+NL+PT, devises, TVA rates), validator (totaux HT+TVA=TTC, dates, confidence), tâche Celery `invoice.process_ocr` avec retry exponentiel, endpoint `/health/worker`.

### Sprint 3 — Review UI
Page `/invoices/[id]` split-view PDF + formulaire éditable (react-pdf), `InvoiceLinesEditor` add/remove/edit, validations live, boutons Confirm/Reject/Skip/Reopen, historique corrections (`InvoiceCorrection`), transitions de statut documentées dans ADR 0002.

### Sprint 4 — Export + Dashboard + Staging
Export Excel formaté (openpyxl, totaux SUM, colonnes figées), KPIs dashboard par statut, filtres pills, pagination, middleware logging request_id, endpoint `/metrics`, docker-compose.prod + Nginx reverse proxy, script deploy.sh, runbook complet.

### P2-A — Ingestion Outlook
Microsoft Graph via `msal`, OAuth delegated (Mail.Read + offline_access), Celery Beat toutes 15 min, ingestion auto PDF/JPG/PNG attachés dans l'Inbox, refresh token transparent.

### P2-B — Connecteur myDATA
Interface `MyDataConnector` pluggable, 3 implémentations (Epsilon Digital, SoftOne myDATA, AADE direct), générateur XML AADE conforme schéma v1.0.x (codes TVA grecs 24%→1, 13%→2, 6%→3, 0%→7), mapper Invoice → InvoiceData, auto-submit après confirm, table `mydata_submissions` avec MARK AADE. **⚠️ Stubs Epsilon/SoftOne à ajuster selon docs éditeur**.

### P2-C — SoftOne ERP sync
Client SoftOne (login → authenticate → setData), mapper Invoice → FINDOC/ITELINES, `find_supplier_by_vat` pour TRDR lookup, auto-export après confirm, table `erp_exports`. **⚠️ Série FINDOC hardcodée à 1000, à rendre configurable**.

### P2-D — Permissions granulaires + audit
Rôles étendus **admin / reviewer / viewer** (user legacy), RBAC appliqué sur tous endpoints sensibles (intégrations = admin, mutations factures = reviewer+, lecture = viewer+), audit automatique sur login/confirm/reject/reopen/user.*, endpoint `/audit` paginé, pages `/admin/users` (invite + password temporaire) et `/admin/audit`, nav conditionnelle.

### P2-E — Gmail + Google Drive
OAuth Google (client httpx), scopes dynamiques selon intent (`gmail.readonly` ou `drive.readonly`), fetch Gmail via `has:attachment` query, Drive via polling dossier + `modifiedTime > last_sync`, tasks `email.sync_gmail` + `drive.sync_gdrive`, scheduler toutes 15 min, UI 3 cards (Outlook/Gmail/Drive) avec input folder_id pour Drive, listes séparées.

## Bugs production débloqués pendant la mise en service

1. **ERR_UNSAFE_PORT** — Chrome/Firefox bloquent le port 6000 (réservé X11). Backend déplacé sur 6200.
2. **passlib/bcrypt ≥5** — incompatibilité au chargement du module. Pin `bcrypt<5` dans `backend/pyproject.toml`.
3. **SQLAlchemy enum** — envoyait les noms Python (`ADMIN`) au lieu des valeurs PG (`admin`). Patch `values_callable=lambda x: [e.value for e in x]` sur les 8 enums (user_role, invoice_status, email_provider, mydata_*, erp_*, cloud_drive_provider).

## ADRs écrites

| # | Sujet | Fichier |
|---|---|---|
| 0001 | Stratégie retry OCR | `docs/adr/0001-ocr-retry-strategy.md` |
| 0002 | Matrice transitions Invoice | `docs/adr/0002-invoice-status-transitions.md` |
| 0003 | Stratégie connecteur myDATA | `docs/adr/0003-mydata-connector-strategy.md` |
| 0004 | Intégration SoftOne ERP | `docs/adr/0004-erp-integration-softone.md` |

## Endpoints actifs

### Auth
`POST /auth/register`, `/login`, `/refresh`, `GET /auth/me`

### Invoices
`POST /invoices/upload` · `GET /invoices` (filtres+pagination) · `GET /invoices/stats` ·
`GET /invoices/:id` · `PATCH /:id` · `POST /:id/confirm|reject|skip|reopen` ·
`GET /:id/corrections` · `GET /:id/mydata` · `POST /:id/mydata/submit` ·
`GET /:id/erp` · `POST /:id/erp/export`

### Exports + metrics + audit
`GET /exports/excel?from&to&supplier_id&status_filter` · `GET /metrics` · `GET /audit`

### Users (admin)
`GET/POST /users` · `PATCH/DELETE /users/:id`

### Integrations (admin)
`POST /integrations/outlook/authorize` · `POST /integrations/gmail/authorize` ·
`POST /integrations/gdrive/authorize?folder_id=` · `GET /google/callback` (public) ·
`GET/PUT/DELETE /integrations/mydata` · `GET/PUT/DELETE /integrations/erp` ·
`GET /integrations/email-sources`, `/gdrive-sources` · `POST /:id/sync` · `DELETE /:id`

### Health
`GET /health` · `GET /health/db` · `GET /health/worker`

## Reste à faire

### Phase 2 (complétion)
- **P2-F** — Epsilon Net ERP (2ème ERP, enum déjà prévu)

### Avant déploiement pilote client
- Valider URLs Epsilon Digital / SoftOne myDATA avec docs éditeur (stubs)
- Tester `aade_direct` sur `mydataapidev.aade.gr` avec compte dev
- Générer vrai `ENCRYPTION_KEY` Fernet + `JWT_SECRET` 64 chars
- Configurer Azure AD app (Outlook) + Google Cloud OAuth (Gmail/Drive)
- Configurer Azure DI (endpoint + key + région UE)
- Contracter un connecteur myDATA ou compte AADE direct
- Obtenir sample factures client → lancer `scripts/ocr-test/` → valider go/no-go
- Nettoyer les 2 pins temporaires (bcrypt, values_callable — celui-ci reste permanent)

### Phase 2+ (non-MVP)
- Détection fraude / anomalies
- ML sur corrections (fine-tuning modèle OCR)
- Mobile app
- API publique pour intégrations tierces
- Multi-devise (mapping SOCURRENCY SoftOne)
- Classification revenus AADE (incomeClassification) — émetteur de factures

## Hors scope MVP

Le contrat cadre (cadrage S1 question 4) prévoyait un forfait MVP avec transfert de propriété. La phase 2 actuellement livrée doit faire l'objet d'un **devis séparé** avec jalons. Découpage recommandé :

- **Phase 2a** (livrée) — Outlook + myDATA + SoftOne + permissions + Gmail + Drive
- **Phase 2b** (à chiffrer) — Epsilon Net + détection doublons ERP + multi-devise
- **Phase 2c** (à chiffrer) — ML corrections + mobile + API publique

---

_Mise à jour : 2026-04-22_
