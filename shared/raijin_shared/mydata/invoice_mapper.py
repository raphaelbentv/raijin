"""Convertit une Invoice interne → InvoiceData pour le générateur XML AADE."""
from __future__ import annotations

from decimal import Decimal

from raijin_shared.models.invoice import Invoice
from raijin_shared.mydata.xml_builder import (
    InvoiceData,
    InvoiceLineData,
    Party,
    vat_category_from_rate,
)


class InvoiceMappingError(ValueError):
    pass


def _strip_country_prefix(vat: str | None) -> str:
    if not vat:
        return ""
    v = vat.strip().upper()
    if v[:2].isalpha():
        return v[2:]
    return v


def _parse_series_and_number(invoice_number: str | None) -> tuple[str, str]:
    if not invoice_number:
        return "0", "0"
    raw = invoice_number.strip()
    if "-" in raw:
        parts = raw.rsplit("-", 1)
        return parts[0] or "0", parts[1] or "0"
    if "/" in raw:
        parts = raw.rsplit("/", 1)
        return parts[0] or "0", parts[1] or "0"
    return "0", raw


def map_invoice_to_mydata(
    invoice: Invoice,
    *,
    issuer_vat_number: str,
) -> InvoiceData:
    """Convertit une Invoice validée en structure InvoiceData prête à XML."""
    if not invoice.issue_date:
        raise InvoiceMappingError("missing_issue_date")
    if invoice.total_ttc is None or invoice.total_vat is None or invoice.total_ht is None:
        raise InvoiceMappingError("missing_totals")

    series, number = _parse_series_and_number(invoice.invoice_number)

    issuer = Party(vat_number=_strip_country_prefix(issuer_vat_number))

    counterpart: Party | None = None
    if invoice.supplier and invoice.supplier.vat_number:
        counterpart = Party(
            vat_number=_strip_country_prefix(invoice.supplier.vat_number),
            country=invoice.supplier.country_code or "GR",
            name=invoice.supplier.name,
        )

    lines: list[InvoiceLineData] = []
    if invoice.lines:
        for line in invoice.lines:
            if line.line_total_ht is None:
                continue
            vat_rate = line.vat_rate or Decimal("0.24")
            vat_amount = (line.line_total_ht * vat_rate).quantize(Decimal("0.01"))
            lines.append(
                InvoiceLineData(
                    line_number=line.line_number,
                    net_value=line.line_total_ht,
                    vat_category=vat_category_from_rate(vat_rate),
                    vat_amount=vat_amount,
                    description=line.description,
                    quantity=line.quantity,
                )
            )
    else:
        # Ligne synthétique : total HT + TVA dans une unique ligne
        inferred_rate = (invoice.total_vat / invoice.total_ht) if invoice.total_ht else Decimal("0")
        inferred_rate_q = inferred_rate.quantize(Decimal("0.01"))
        lines.append(
            InvoiceLineData(
                line_number=1,
                net_value=invoice.total_ht,
                vat_category=vat_category_from_rate(inferred_rate_q),
                vat_amount=invoice.total_vat,
                description=invoice.source_file_name,
            )
        )

    return InvoiceData(
        series=series,
        number=number,
        issue_date=invoice.issue_date,
        currency=invoice.currency or "EUR",
        issuer=issuer,
        counterpart=counterpart,
        lines=lines,
        total_net=invoice.total_ht,
        total_vat=invoice.total_vat,
        total_gross=invoice.total_ttc,
    )
