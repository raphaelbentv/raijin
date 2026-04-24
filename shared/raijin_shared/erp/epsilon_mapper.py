"""Convertit une Invoice Raijin → payload JSON Epsilon Net document."""
from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from raijin_shared.models.invoice import Invoice


class EpsilonMappingError(ValueError):
    pass


def _dec(value: Decimal | None) -> float:
    if value is None:
        return 0.0
    return float(value.quantize(Decimal("0.01")))


def _vat_pct(rate: Decimal | None) -> float:
    if rate is None:
        return 24.0
    return float((rate * 100).quantize(Decimal("0.01")))


def map_invoice_to_epsilon(
    invoice: "Invoice",
    *,
    document_type: str = "PURCHASE_INVOICE",
    series: str = "A",
    supplier_external_id: str | None = None,
) -> dict:
    """Génère un payload JSON pour POST /api/v1/documents Epsilon Net.

    - ``document_type`` : type Epsilon (PURCHASE_INVOICE, CREDIT_NOTE, etc.)
    - ``series`` : série du document côté Epsilon
    - ``supplier_external_id`` : ID Epsilon du fournisseur (résolu par VAT)
    """
    if not invoice.issue_date:
        raise EpsilonMappingError("missing_issue_date")
    if invoice.total_ttc is None:
        raise EpsilonMappingError("missing_total_ttc")

    supplier_block: dict = {}
    if invoice.supplier:
        supplier_block = {
            "name": invoice.supplier.name,
            "vatNumber": invoice.supplier.vat_number,
            "country": invoice.supplier.country_code or "GR",
        }
        if supplier_external_id:
            supplier_block["externalId"] = supplier_external_id
        if invoice.supplier.city:
            supplier_block["city"] = invoice.supplier.city

    lines: list[dict] = []
    if invoice.lines:
        for line in invoice.lines:
            if line.line_total_ht is None:
                continue
            lines.append(
                {
                    "lineNumber": line.line_number,
                    "description": (line.description or "Article")[:250],
                    "quantity": float(line.quantity) if line.quantity else 1.0,
                    "unitPrice": _dec(line.unit_price),
                    "vatRate": _vat_pct(line.vat_rate),
                    "netAmount": _dec(line.line_total_ht),
                    "grossAmount": _dec(line.line_total_ttc),
                }
            )
    else:
        inferred_rate = (
            (invoice.total_vat / invoice.total_ht)
            if invoice.total_ht and invoice.total_vat is not None
            else Decimal("0.24")
        )
        lines.append(
            {
                "lineNumber": 1,
                "description": invoice.source_file_name[:250],
                "quantity": 1.0,
                "unitPrice": _dec(invoice.total_ht),
                "vatRate": _vat_pct(inferred_rate),
                "netAmount": _dec(invoice.total_ht),
                "grossAmount": _dec(invoice.total_ttc),
            }
        )

    return {
        "document": {
            "type": document_type,
            "series": series,
            "number": invoice.invoice_number or "",
            "issueDate": invoice.issue_date.isoformat(),
            "dueDate": invoice.due_date.isoformat() if invoice.due_date else None,
            "currency": invoice.currency or "EUR",
            "supplier": supplier_block,
            "lines": lines,
            "totals": {
                "netAmount": _dec(invoice.total_ht),
                "vatAmount": _dec(invoice.total_vat),
                "grossAmount": _dec(invoice.total_ttc),
            },
            "reference": {
                "source": "raijin",
                "externalRef": str(invoice.id),
                "originalFilename": invoice.source_file_name,
            },
        }
    }
