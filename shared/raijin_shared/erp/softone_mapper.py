"""Convertit une Invoice Raijin → payload SoftOne FINDOC."""
from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from raijin_shared.models.invoice import Invoice


class SoftOneMappingError(ValueError):
    pass


def _decimal_to_float(value: Decimal | None) -> float:
    if value is None:
        return 0.0
    return float(value.quantize(Decimal("0.01")))


def _vat_rate_percent(rate: Decimal | None) -> int:
    if rate is None:
        return 24
    return int((rate * 100).quantize(Decimal("1")))


def map_invoice_to_softone(
    invoice: Invoice,
    *,
    series: int = 1000,
    payment_terms: int = 1,
    currency_code: int = 1,
    trdr_external_id: str | int | None = None,
) -> dict:
    """Génère le payload JSON pour POST setData FINDOC.

    - ``series`` : série de facturation configurée dans SoftOne
    - ``payment_terms`` : code FPRMS (par défaut 1 = cash)
    - ``currency_code`` : 1 = EUR en GR (à ajuster si autre devise)
    - ``trdr_external_id`` : ID SoftOne du fournisseur (résolu côté connecteur)
    """
    if not invoice.issue_date:
        raise SoftOneMappingError("missing_issue_date")
    if invoice.total_ttc is None:
        raise SoftOneMappingError("missing_total_ttc")

    findoc_row = {
        "SERIES": series,
        "FINCODE": invoice.invoice_number or "",
        "TRNDATE": invoice.issue_date.isoformat(),
        "FPRMS": payment_terms,
        "SOCURRENCY": currency_code,
        "COMMENTS": f"Raijin import — {invoice.source_file_name}",
    }
    if trdr_external_id is not None:
        findoc_row["TRDR"] = int(trdr_external_id) if str(trdr_external_id).isdigit() else trdr_external_id

    if invoice.total_ht is not None:
        findoc_row["SUMAMNT"] = _decimal_to_float(invoice.total_ht)
    if invoice.total_vat is not None:
        findoc_row["VATAMNT"] = _decimal_to_float(invoice.total_vat)
    findoc_row["GRAMNT"] = _decimal_to_float(invoice.total_ttc)

    if invoice.due_date:
        findoc_row["PAYDATE"] = invoice.due_date.isoformat()

    lines: list[dict] = []
    if invoice.lines:
        for line in invoice.lines:
            lines.append(
                {
                    "MTRL": 0,
                    "CCCMATERIAL": (line.description or "Raijin item")[:250],
                    "QTY1": _decimal_to_float(line.quantity or Decimal("1")),
                    "PRICE": _decimal_to_float(line.unit_price),
                    "VATRTE": _vat_rate_percent(line.vat_rate),
                    "LINEVAL": _decimal_to_float(line.line_total_ht),
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
                "MTRL": 0,
                "CCCMATERIAL": invoice.source_file_name[:250],
                "QTY1": 1.0,
                "PRICE": _decimal_to_float(invoice.total_ht),
                "VATRTE": _vat_rate_percent(inferred_rate),
                "LINEVAL": _decimal_to_float(invoice.total_ht),
            }
        )

    return {"FINDOC": [findoc_row], "ITELINES": lines}
