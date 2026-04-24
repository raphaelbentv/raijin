# ADR 0002 — Matrice des transitions de statut Invoice

**Statut** : Accepté — 2026-04-21
**Contexte** : Sprint 3, Review UI

## Matrice des transitions autorisées

| De \ Vers         | uploaded | processing | ready_for_review | confirmed | rejected | failed |
|-------------------|----------|------------|------------------|-----------|----------|--------|
| **uploaded**      | —        | ✅ worker  | —                | —         | —        | —      |
| **processing**    | —        | —          | ✅ worker        | —         | ✅ user* | ✅ worker |
| **ready_for_review** | —     | —          | (self / skip)    | ✅ user   | ✅ user  | —      |
| **confirmed**     | —        | —          | ✅ reopen        | —         | —        | —      |
| **rejected**      | —        | —          | ✅ reopen/edit   | —         | —        | —      |
| **failed**        | —        | —          | —                | —         | —        | —      |

\* user peut rejeter une facture en `processing` (abort manuel).

## Endpoints correspondants

- `PATCH /invoices/:id` → autorisé si `status ∈ {ready_for_review, rejected}` (passe auto rejected → ready_for_review)
- `POST /invoices/:id/confirm` → autorisé si `status == ready_for_review` ET `validation_errors` ne contient pas d'error
- `POST /invoices/:id/reject` → autorisé si `status ∈ {ready_for_review, processing}`
- `POST /invoices/:id/skip` → autorisé si `status == ready_for_review` (bump updated_at, reste en review)
- `POST /invoices/:id/reopen` → autorisé si `status ∈ {confirmed, rejected}`

## Règles de validation bloquantes

Une confirmation est **refusée (HTTP 422)** si `validation_errors.issues` contient un élément avec `severity == "error"`. Les warnings n'empêchent pas la confirmation.

Règles d'erreur :
- `missing_vendor_name`, `missing_invoice_date`
- `totals_mismatch` (HT + TVA ≠ TTC à ±0.02)
- `subtotal_gt_total`
- `missing_invoice_total`
- `issue_after_due`
- `low_confidence` (< 0.70)

Règles de warning :
- `missing_invoice_id`
- `medium_confidence` (0.70–0.90)
- `issue_date_future` (>7 jours futurs)
- `possible_duplicate`

## Historique des corrections

Table `invoice_corrections` capture `(field, before_value, after_value, user_id, timestamp)` pour les champs trackés (`invoice_number`, `issue_date`, `due_date`, `currency`, `total_ht`, `total_vat`, `total_ttc`, `supplier_id`). Non-capturé : modifications de lignes (visibles via `updated_at`).

Usage : audit, fine-tuning futur (les corrections humaines constituent un dataset de vérité-terrain).
