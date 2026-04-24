# 🔥 OCR Test — Go/No-Go technique

Script isolé pour valider la qualité d'Azure Document Intelligence sur un échantillon de factures réelles du client.

## Principe

Ce script est **indépendant du backend Raijin**. Il lit un dossier de factures, appelle Azure DI `prebuilt-invoice`, et produit :

1. Un JSON par facture avec les champs extraits et leur confidence
2. Un rapport markdown agrégé avec les moyennes par champ critique

C'est un **go/no-go** : si Azure DI n'atteint pas ≥ 90% d'accuracy sur les champs critiques (fournisseur, VAT, totaux, dates), il faut pivoter vers un plan B (Google Document AI, Mindee, custom model).

## Installation

```bash
cd scripts/ocr-test
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Configuration

Crée `.env` avec :

```bash
AZURE_DI_ENDPOINT=https://<resource>.cognitiveservices.azure.com/
AZURE_DI_KEY=<your-key>
AZURE_DI_MODEL=prebuilt-invoice
AZURE_DI_LOCALE=el-GR
```

## Usage

```bash
# Dépose tes factures dans samples/ (PDF, JPG, PNG)
mkdir -p samples reports
cp /path/to/invoices/*.pdf samples/

# Lance l'analyse
python run_ocr_test.py

# Les résultats atterrissent dans reports/
ls reports/
# - <filename>.json    (extraction brute)
# - summary.md         (rapport agrégé)
```

## Champs évalués

- `vendor_name` — nom fournisseur
- `vendor_tax_id` — VAT number
- `invoice_id` — numéro facture
- `invoice_date` — date émission
- `due_date` — date échéance
- `subtotal` — total HT
- `total_tax` — total TVA
- `invoice_total` — total TTC
- `items` — lignes de facture

## Interprétation

| Confidence moyenne | Verdict |
|--------------------|---------|
| ≥ 0.90             | Go — qualité production |
| 0.80 – 0.90        | Orange — validation humaine systématique |
| < 0.80             | No-go — pivoter vers plan B |
