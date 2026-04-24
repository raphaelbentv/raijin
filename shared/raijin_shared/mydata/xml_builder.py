"""Générateur XML AADE myDATA (schéma public v1.0.x).

Référence officielle : https://www.aade.gr/mydata (schémas XSD publiés par AADE).
Cette implémentation couvre le cas nominal — facture nationale grecque
simplifiée (un contrepartie, montants en EUR, TVA cat 1/2/3 codes AADE).

Les éléments non implémentés (paiements multiples, facturation internationale,
factures auto-facturées, etc.) devront être enrichis au cas par cas.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from xml.etree.ElementTree import Element, SubElement, tostring

NS_ENV = "http://www.aade.gr/myDATA/invoice/v1.0"
NS_ICLS = "https://www.aade.gr/myDATA/incomeClassificaton/v1.0"
NS_XSI = "http://www.w3.org/2001/XMLSchema-instance"

# Codes VAT AADE (partiel — complet dans la doc officielle)
VAT_CATEGORY_CODES = {
    # ratio (0 → code) — Grèce 2026 : 24% standard, 13% réduit, 6% super-réduit, 0% exempté
    "0.24": 1,  # 24% VAT
    "0.13": 2,  # 13%
    "0.06": 3,  # 6%
    "0.00": 7,  # 0% / exempt
    "0": 7,
}


@dataclass
class Party:
    vat_number: str  # sans préfixe EL
    country: str = "GR"
    branch: int = 0
    name: str | None = None


@dataclass
class InvoiceLineData:
    line_number: int
    net_value: Decimal
    vat_category: int  # code AADE
    vat_amount: Decimal
    description: str | None = None
    quantity: Decimal | None = None


@dataclass
class InvoiceData:
    series: str           # série (ex. "A")
    number: str           # numéro facture
    issue_date: date
    currency: str = "EUR"
    invoice_type: str = "1.1"  # 1.1 = facture de vente biens/services (code AADE)
    issuer: Party = field(default_factory=lambda: Party(vat_number=""))
    counterpart: Party | None = None  # None si vente à particulier
    lines: list[InvoiceLineData] = field(default_factory=list)
    total_net: Decimal = Decimal("0")
    total_vat: Decimal = Decimal("0")
    total_gross: Decimal = Decimal("0")


def vat_category_from_rate(rate: Decimal | None) -> int:
    if rate is None:
        return 7
    key = format(rate, "f").rstrip("0").rstrip(".")
    return VAT_CATEGORY_CODES.get(format(rate, ".2f"), VAT_CATEGORY_CODES.get(key, 8))


def _decimal(value: Decimal | None) -> str:
    if value is None:
        return "0.00"
    q = value.quantize(Decimal("0.01"))
    return format(q, "f")


def _set(parent: Element, tag: str, value) -> Element:
    el = SubElement(parent, f"{{{NS_ENV}}}{tag}")
    el.text = str(value) if value is not None else ""
    return el


def _set_party(parent: Element, tag: str, party: Party) -> Element:
    el = SubElement(parent, f"{{{NS_ENV}}}{tag}")
    _set(el, "vatNumber", party.vat_number)
    _set(el, "country", party.country)
    _set(el, "branch", str(party.branch))
    if party.name:
        _set(el, "name", party.name)
    return el


def build_invoices_doc_xml(invoices: list[InvoiceData]) -> bytes:
    """Génère un document XML InvoicesDoc pour une liste de factures.

    Retourne les bytes prêts à être POSTés au connecteur / AADE.
    """
    ns_map = {
        "xmlns": NS_ENV,
        "xmlns:icls": NS_ICLS,
        "xmlns:xsi": NS_XSI,
    }
    root = Element(f"{{{NS_ENV}}}InvoicesDoc", ns_map)

    for inv in invoices:
        inv_el = SubElement(root, f"{{{NS_ENV}}}invoice")

        # Issuer (émetteur)
        _set_party(inv_el, "issuer", inv.issuer)

        # Counterpart (client), optionnel
        if inv.counterpart:
            _set_party(inv_el, "counterpart", inv.counterpart)

        # Invoice header
        header = SubElement(inv_el, f"{{{NS_ENV}}}invoiceHeader")
        _set(header, "series", inv.series or "0")
        _set(header, "aa", inv.number or "0")
        _set(header, "issueDate", inv.issue_date.isoformat())
        _set(header, "invoiceType", inv.invoice_type)
        _set(header, "currency", inv.currency)

        # Details (lignes)
        for line in inv.lines:
            details = SubElement(inv_el, f"{{{NS_ENV}}}invoiceDetails")
            _set(details, "lineNumber", str(line.line_number))
            _set(details, "netValue", _decimal(line.net_value))
            _set(details, "vatCategory", str(line.vat_category))
            _set(details, "vatAmount", _decimal(line.vat_amount))
            if line.quantity is not None:
                _set(details, "quantity", _decimal(line.quantity))
            if line.description:
                _set(details, "lineComments", line.description[:100])

        # Summary
        summary = SubElement(inv_el, f"{{{NS_ENV}}}invoiceSummary")
        _set(summary, "totalNetValue", _decimal(inv.total_net))
        _set(summary, "totalVatAmount", _decimal(inv.total_vat))
        _set(summary, "totalWithheldAmount", "0.00")
        _set(summary, "totalFeesAmount", "0.00")
        _set(summary, "totalStampDutyAmount", "0.00")
        _set(summary, "totalOtherTaxesAmount", "0.00")
        _set(summary, "totalDeductionsAmount", "0.00")
        _set(summary, "totalGrossValue", _decimal(inv.total_gross))

    return b'<?xml version="1.0" encoding="UTF-8"?>\n' + tostring(root, encoding="utf-8")
