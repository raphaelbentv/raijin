# ADR 0003 — Stratégie myDATA (AADE)

**Statut** : Accepté — 2026-04-21
**Contexte** : Phase 2 — conformité fiscale grecque myDATA

## Décision

Architecture **pluggable** avec une interface `MyDataConnector` et trois implémentations :

1. **`epsilon_digital`** — via connecteur certifié Epsilon Digital (REST JSON, auth Bearer)
2. **`softone_mydata`** — via connecteur certifié SoftOne myDATA (REST JSON, auth client-id/secret/subscription)
3. **`aade_direct`** — intégration directe AADE API (POST XML, headers `aade-user-id` + `Ocp-Apim-Subscription-Key`)

Un seul connecteur actif par tenant (unique constraint `mydata_connectors.tenant_id`). Credentials stockés **chiffrés symétrique Fernet** (`credentials_encrypted` text) avec clé `ENCRYPTION_KEY` env. Jamais renvoyés au client.

## Pourquoi cette approche

- **Cadrage S1 (question 8)** recommandait l'**Option A — connecteur certifié** pour minimiser le risque conformité. On garde cette voie principale (Epsilon ou SoftOne) sans fermer la porte à l'intégration directe AADE pour les clients plus techniques ou indépendants.
- **Dette fonctionnelle maîtrisée** : les 3 implémentations sont livrées comme stubs fonctionnels — les URLs et schémas JSON précis devront être ajustés quand le contrat commercial est signé avec Epsilon/SoftOne (docs API privées).
- **Test dev sans cost** : `aade_direct` pointé vers l'endpoint dev AADE (`mydataapidev.aade.gr`) permet des essais E2E sans contrat commercial.
- **Génération XML centralisée** : `shared/raijin_shared/mydata/xml_builder.py` est conforme au schéma public AADE v1.0.x (InvoicesDoc avec issuer, counterpart, header, details, summary). Les 3 connecteurs reçoivent le même XML — seul le transport diffère.

## Flow production

```
User confirme une facture
  → backend confirm_invoice
  → _maybe_enqueue_mydata (si connector.is_active ET connector.auto_submit)
  → Celery send_task("mydata.submit_invoice", invoice_id)
Worker pick up
  → load Invoice + Supplier + Lines
  → InvoiceMapper → InvoiceData
  → xml_builder → bytes XML
  → factory.build_connector(connector_row) → MyDataConnector
  → connector.submit(xml) → SubmitResult (external_id, aade_mark, uid)
  → persist MyDataSubmission avec status:
     · acknowledged (si aade_mark reçu)
     · submitted (succès mais mark pas encore)
     · failed (si permanent) → retry pour transient (max 5, backoff exp)
```

## Mapping VAT → code AADE

| Taux | Code AADE |
|------|-----------|
| 0,24 (24%) | 1 |
| 0,13 (13%) | 2 |
| 0,06 (6%)  | 3 |
| 0,00 (0%)  | 7 (exonéré) |

Autres codes (transport exempt, zero-rating specific) non implémentés — à ajouter au cas par cas.

## Credentials par connecteur

```json
// epsilon_digital
{"api_key": "..."}

// softone_mydata
{"client_id": "...", "client_secret": "...", "subscription_id": "..."}

// aade_direct
{"user_id": "...", "subscription_key": "..."}
```

## Points ouverts avant production

1. **Valider les URLs et schémas JSON** Epsilon/SoftOne avec la doc éditeur (stubs sinon)
2. **Tester `aade_direct` en environnement dev AADE** (endpoint `mydataapidev.aade.gr`) avec un compte test
3. **Gestion des factures d'achat** (`invoiceType` 1.1 / 2.1 selon sens — actuellement hardcodé 1.1)
4. **Classification des revenus (incomeClassification)** — schéma AADE demande des codes spécifiques par ligne pour les émetteurs grecs, à ajouter quand on émet des factures (pas juste fournisseur)
5. **Cancellation / correction (CancelInvoice)** — pas implémenté, AADE demande un flow d'annulation formel
6. **Rate limit AADE** : 600 req/5 min en prod — le retry backoff actuel (30→600s) est conservateur mais il faudra un throttle si volume > 100/h

## Statuts de soumission

| Status | Signification |
|--------|---------------|
| `pending` | Tâche créée, pas encore submit |
| `submitted` | Envoyé au connecteur, réponse OK mais pas de MARK AADE encore |
| `acknowledged` | MARK AADE reçu → conforme |
| `failed` | Rejet définitif (erreur métier/validation) |
| `cancelled` | Annulation manuelle (pas implémentée) |
