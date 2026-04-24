# ADR 0004 — Intégration ERP (SoftOne prioritaire)

**Statut** : Accepté — 2026-04-21
**Contexte** : Phase 2 — export factures validées vers ERP comptable

## Décision

Interface `ErpConnector` (Protocol) avec factory selon `ErpConnectorKind` enum. Une seule implémentation active à ce jour : **SoftOne** (Genesis / Atlantis / Cloud). Epsilon Net planifié phase 2 ultérieure.

## Architecture

```
backend confirm_invoice
  → _maybe_enqueue_erp (si connector.is_active ET connector.auto_export)
  → Celery send_task("erp.export_invoice", invoice_id)
Worker
  → load Invoice + Supplier + Lines
  → factory.build_erp_connector(connector_row) → SoftOneConnector
  → (optionnel) connector.find_supplier_by_vat(invoice.supplier.vat_number) → TRDR id
  → map_invoice_to_softone(invoice, trdr_external_id=TRDR) → payload FINDOC/ITELINES
  → connector.export_invoice(payload) → ExportResult
  → persist ErpExport(status=acknowledged, external_id=FINDOC id)
```

## Flow SoftOne web services

1. `POST /s1services` `{"service":"login","username","password","appId"}` → `clientID` initial
2. `POST /s1services` `{"service":"authenticate","clientID","company","branch","module","refid"}` → `clientID` authentifié
3. `POST /s1services` `{"service":"setData","clientID","object":"FINDOC","form":"FINDOC","data":{FINDOC: [...], ITELINES: [...]}}` → création doc
4. (optionnel) `POST /s1services` `{"service":"getData","object":"TRDR","filter":{"AFM":VAT}}` → résoudre supplier

Session `clientID` gardée en mémoire par instance (cycle de vie = tâche Celery). Pas de cache partagé : acceptable au MVP tant que volume < 500 exports/jour.

## Credentials (chiffrés Fernet)

```json
{"username": "admin", "password": "...", "app_id": "3001"}
```

Config optionnelle (table `erp_connectors.config` JSONB) :
- `company` (défaut 1)
- `branch` (défaut 1)
- `module` (défaut 0)
- `refid` (défaut 1)
- `object` (défaut "FINDOC")
- `form` (défaut "FINDOC")

## Mapping FINDOC

Payload généré par `shared/raijin_shared/erp/softone_mapper.py` :

```json
{
  "FINDOC": [{
    "SERIES": 1000,
    "FINCODE": "INV-001",
    "TRNDATE": "2026-04-21",
    "TRDR": 1234,
    "FPRMS": 1,
    "SOCURRENCY": 1,
    "SUMAMNT": 100.00,
    "VATAMNT": 24.00,
    "GRAMNT": 124.00,
    "PAYDATE": "2026-05-21",
    "COMMENTS": "Raijin import — facture.pdf"
  }],
  "ITELINES": [{
    "MTRL": 0,
    "CCCMATERIAL": "Consulting",
    "QTY1": 1.0,
    "PRICE": 100.00,
    "VATRTE": 24,
    "LINEVAL": 100.00
  }]
}
```

- `MTRL: 0` = ligne en texte libre (pas d'item catalogue)
- `VATRTE` en **pourcentage entier** (pas ratio)
- `SOCURRENCY: 1` = EUR (1 en config GR par défaut)

## Points ouverts avant production

1. **Série FINDOC** — actuellement hardcodée à `1000`. À rendre configurable par tenant selon config SoftOne client (certaines sociétés utilisent 3000 pour achats).
2. **Mapping MTRL** — MVP en texte libre ; si le client veut synchroniser avec son catalogue items, ajouter `sync_items` + matching par SKU.
3. **Classification comptable** — SoftOne demande éventuellement `ACN`, `CCCMATERIAL` plus riches pour la ventilation compte.
4. **Devise non-EUR** — support seulement EUR (`SOCURRENCY: 1`). Mapping currency → code SoftOne à ajouter si multi-devise.
5. **Gestion des doublons** — pas de check avant export. Si `erp_exports` a déjà `acknowledged`, ne pas re-soumettre (à ajouter).
6. **Rate limit SoftOne** — pas de spec publique, prévoir throttle si volume > 1000/jour.

## Tests

- `backend/tests/test_softone_mapper.py` : couverture cases avec lignes, sans lignes, issue_date manquante.
- `workers/services/erp/softone.py` : testable avec mock `requests` (pas inclus — intégration à valider en staging avec credentials client réels).
