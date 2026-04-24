# ADR 0005 — Intégration Epsilon Net

**Statut** : Accepté — 2026-04-22
**Contexte** : Phase 2 — second ERP après SoftOne

## Décision

Ajout d'un second `ErpConnector` pour **Epsilon Net** (produits Pylon, Hypersoft, Digital Accounting). Implémentation REST JSON moderne (plus simple que SoftOne). Active l'option "Epsilon Net" dans l'UI `<ErpCard>` (précédemment désactivée).

## API Epsilon Net (hypothèse stub)

- **Base URL** : définie par tenant (ex. `https://api.epsilon-net.gr`)
- **Auth** : header `Authorization: Bearer <api_key>` + header `X-Subscription-Id`
- **Option** : `X-Company-Id` si le compte Epsilon gère plusieurs sociétés
- **POST** `/api/v1/documents` avec payload JSON `{ document: { ... } }` — création d'un document d'achat
- **GET** `/api/v1/suppliers?vat=XXX&limit=1` — résolution fournisseur (best-effort)

⚠️ **URLs et schémas sont stubs** — à valider avec la doc éditeur réelle quand contrat commercial signé.

## Payload document

```json
{
  "document": {
    "type": "PURCHASE_INVOICE",
    "series": "A",
    "number": "INV-001",
    "issueDate": "2026-04-21",
    "dueDate": "2026-05-21",
    "currency": "EUR",
    "supplier": {
      "name": "Acme SA",
      "vatNumber": "EL123456789",
      "country": "GR",
      "externalId": "SUP-42",
      "city": "Athens"
    },
    "lines": [
      {
        "lineNumber": 1,
        "description": "Prestation",
        "quantity": 1,
        "unitPrice": 100.00,
        "vatRate": 24.0,
        "netAmount": 100.00,
        "grossAmount": 124.00
      }
    ],
    "totals": {
      "netAmount": 100.00,
      "vatAmount": 24.00,
      "grossAmount": 124.00
    },
    "reference": {
      "source": "raijin",
      "externalRef": "<invoice_id>",
      "originalFilename": "facture.pdf"
    }
  }
}
```

Mapping Raijin → Epsilon implémenté dans `shared/raijin_shared/erp/epsilon_mapper.py`. Diff avec SoftOne :
- VAT en **pourcentage float** (24.0 au lieu de 24)
- Clés **camelCase** REST (pas `VATRTE`, `GRAMNT`…)
- `type: PURCHASE_INVOICE` explicite
- `supplier` imbriqué avec tous les champs, plutôt qu'un `TRDR` numeric

## Credentials (chiffrés Fernet)

```json
{"api_key": "...", "subscription_id": "..."}
```

Config optionnelle : `{"company_id": "..."}` si le compte Epsilon gère plusieurs sociétés.

## Flow end-to-end

```
User confirm une facture
  → backend _maybe_enqueue_erp (si connector actif + auto_export)
  → Celery send_task erp.export_invoice
Worker
  → build_erp_connector → EpsilonNetConnector(base_url, api_key, subscription_id, company_id?)
  → optional find_supplier_by_vat → external_id Epsilon
  → map_invoice_to_epsilon → payload JSON
  → connector.export_invoice(payload)
  → persist ErpExport(status=acknowledged, external_id=document.id)
```

## Points ouverts avant production

1. **Valider les routes exactes** avec la doc Epsilon (peut-être `/odata/Documents`, `/api/accounting/purchase-invoice`, etc.)
2. **Rate limit** inconnu — prévoir throttle si volume > 500/jour
3. **Schéma `document.type`** à adapter : PURCHASE_INVOICE est générique, Epsilon utilise peut-être des codes spécifiques (e.g. "EP-01", numéro de type 1.1)
4. **Multi-sociétés** — la tête `X-Company-Id` est ma best-guess ; vérifier si c'est un query param, un body field, ou un path segment
5. **Auth refresh** — pour l'instant api_key statique. Si Epsilon utilise OAuth2 + refresh, adapter le connector

## Priorités client

Si un client utilise déjà Epsilon Net en Grèce, on part sur ce connector (plus simple, JSON moderne, mapping plus clean). Sinon, SoftOne reste le défaut prioritaire (plus répandu).
