from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from typing import Any

from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeResult
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import AzureError, HttpResponseError, ServiceRequestError

from app.core.config import get_settings


class AzureDiError(Exception):
    pass


class AzureDiTransientError(AzureDiError):
    """Transient failure — safe to retry."""


class AzureDiPermanentError(AzureDiError):
    """Permanent failure — do not retry."""


def _mock_extraction(data: bytes) -> ExtractedInvoice:
    suffix = hashlib.sha1(data).hexdigest()[:8].upper()
    return ExtractedInvoice(
        vendor_name="Sprint 5 Supplies",
        vendor_tax_id="FR12345678901",
        vendor_address="10 rue de la Paix, 75002 Paris",
        vendor_country="FR",
        invoice_id=f"SPR5-{suffix}",
        invoice_date="2026-04-20",
        due_date="2026-05-20",
        currency="EUR",
        subtotal=Decimal("100.00"),
        total_tax=Decimal("20.00"),
        invoice_total=Decimal("120.00"),
        lines=[
            ExtractedLine(
                line_number=1,
                description="OCR fixture service",
                quantity=Decimal("1"),
                unit_price=Decimal("100.00"),
                vat_rate=Decimal("0.20"),
                line_total_ht=Decimal("100.00"),
                line_total_ttc=Decimal("120.00"),
                confidence=0.98,
            )
        ],
        field_confidences={
            "VendorName": 0.98,
            "VendorTaxId": 0.97,
            "InvoiceId": 0.99,
            "InvoiceDate": 0.98,
            "SubTotal": 0.99,
            "TotalTax": 0.99,
            "InvoiceTotal": 0.99,
        },
        overall_confidence=0.98,
        raw_payload={"mock": True, "bytes": len(data)},
    )


@dataclass
class ExtractedLine:
    line_number: int
    description: str | None = None
    quantity: Decimal | None = None
    unit_price: Decimal | None = None
    vat_rate: Decimal | None = None
    line_total_ht: Decimal | None = None
    line_total_ttc: Decimal | None = None
    confidence: float | None = None


@dataclass
class ExtractedInvoice:
    vendor_name: str | None = None
    vendor_tax_id: str | None = None
    vendor_address: str | None = None
    vendor_country: str | None = None
    invoice_id: str | None = None
    invoice_date: str | None = None
    due_date: str | None = None
    currency: str | None = None
    subtotal: Decimal | None = None
    total_tax: Decimal | None = None
    invoice_total: Decimal | None = None
    lines: list[ExtractedLine] = field(default_factory=list)
    field_confidences: dict[str, float] = field(default_factory=dict)
    overall_confidence: float | None = None
    raw_payload: dict[str, Any] = field(default_factory=dict)


@lru_cache
def _client() -> DocumentIntelligenceClient:
    settings = get_settings()
    if not settings.azure_di_endpoint or not settings.azure_di_key:
        raise AzureDiPermanentError("azure_di_not_configured")
    return DocumentIntelligenceClient(
        endpoint=settings.azure_di_endpoint,
        credential=AzureKeyCredential(settings.azure_di_key),
    )


def _to_decimal(raw: Any) -> Decimal | None:
    if raw is None:
        return None
    try:
        if isinstance(raw, (int, float, str)):
            return Decimal(str(raw))
        if hasattr(raw, "amount"):
            return Decimal(str(raw.amount))
        return None
    except (InvalidOperation, ValueError):
        return None


def _field_string(document_fields: dict, name: str) -> str | None:
    raw = document_fields.get(name)
    if raw is None:
        return None
    return (
        getattr(raw, "value_string", None)
        or getattr(raw, "value_address", None)
        or getattr(raw, "content", None)
    )


def _field_date(document_fields: dict, name: str) -> str | None:
    raw = document_fields.get(name)
    if raw is None:
        return None
    value = getattr(raw, "value_date", None)
    if value is None:
        return getattr(raw, "content", None)
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def _field_currency(document_fields: dict, name: str) -> tuple[Decimal | None, str | None]:
    raw = document_fields.get(name)
    if raw is None:
        return None, None
    cur = getattr(raw, "value_currency", None)
    if cur is None:
        return _to_decimal(getattr(raw, "content", None)), None
    amount = Decimal(str(cur.amount)) if cur.amount is not None else None
    code = getattr(cur, "currency_code", None)
    return amount, code


def _field_confidence(document_fields: dict, name: str) -> float | None:
    raw = document_fields.get(name)
    if raw is None:
        return None
    return getattr(raw, "confidence", None)


def _extract_lines(document_fields: dict) -> list[ExtractedLine]:
    items = document_fields.get("Items")
    if items is None or not hasattr(items, "value_array"):
        return []

    extracted: list[ExtractedLine] = []
    for index, item in enumerate(items.value_array or [], start=1):
        sub = getattr(item, "value_object", None) or {}
        description = _field_string(sub, "Description")
        quantity = _to_decimal(getattr(sub.get("Quantity"), "value_number", None) if sub.get("Quantity") else None)
        unit_price_cur, _ = _field_currency(sub, "UnitPrice")
        line_total_cur, _ = _field_currency(sub, "Amount")
        vat_rate_raw = sub.get("TaxRate")
        vat_rate = None
        if vat_rate_raw is not None:
            vat_str = getattr(vat_rate_raw, "content", None) or getattr(vat_rate_raw, "value_string", None)
            if vat_str:
                vat_rate = _to_decimal(vat_str.replace("%", "").strip())

        extracted.append(
            ExtractedLine(
                line_number=index,
                description=description,
                quantity=quantity,
                unit_price=unit_price_cur,
                vat_rate=vat_rate,
                line_total_ht=line_total_cur,
                confidence=getattr(item, "confidence", None),
            )
        )
    return extracted


def _parse_analyze_result(result: AnalyzeResult) -> ExtractedInvoice:
    if not result.documents:
        raise AzureDiPermanentError("no_document_detected")

    document = result.documents[0]
    fields = document.fields or {}

    subtotal, _ = _field_currency(fields, "SubTotal")
    total_tax, _ = _field_currency(fields, "TotalTax")
    invoice_total, currency_code = _field_currency(fields, "InvoiceTotal")

    extracted = ExtractedInvoice(
        vendor_name=_field_string(fields, "VendorName"),
        vendor_tax_id=_field_string(fields, "VendorTaxId"),
        vendor_address=_field_string(fields, "VendorAddress"),
        vendor_country=_field_string(fields, "VendorAddressRecipient"),
        invoice_id=_field_string(fields, "InvoiceId"),
        invoice_date=_field_date(fields, "InvoiceDate"),
        due_date=_field_date(fields, "DueDate"),
        currency=currency_code,
        subtotal=subtotal,
        total_tax=total_tax,
        invoice_total=invoice_total,
        lines=_extract_lines(fields),
    )

    critical = [
        "VendorName",
        "VendorTaxId",
        "InvoiceId",
        "InvoiceDate",
        "SubTotal",
        "TotalTax",
        "InvoiceTotal",
    ]
    for name in critical:
        conf = _field_confidence(fields, name)
        if conf is not None:
            extracted.field_confidences[name] = conf

    if extracted.field_confidences:
        extracted.overall_confidence = sum(extracted.field_confidences.values()) / len(
            extracted.field_confidences
        )

    extracted.raw_payload = result.as_dict() if hasattr(result, "as_dict") else {}
    return extracted


def analyze_invoice_bytes(data: bytes) -> ExtractedInvoice:
    """Call Azure DI prebuilt-invoice. Raises AzureDiTransientError or AzureDiPermanentError."""
    settings = get_settings()
    if (
        settings.azure_di_mock_in_development
        and not settings.is_production
        and (not settings.azure_di_endpoint or not settings.azure_di_key)
    ):
        return _mock_extraction(data)
    client = _client()
    try:
        poller = client.begin_analyze_document(
            model_id=settings.azure_di_model,
            body=data,
            locale=settings.azure_di_locale,
            content_type="application/octet-stream",
        )
        result = poller.result(timeout=settings.azure_di_timeout_seconds)
    except ServiceRequestError as exc:
        raise AzureDiTransientError(f"network_error: {exc}") from exc
    except HttpResponseError as exc:
        status = getattr(exc, "status_code", None)
        if status is not None and 500 <= status < 600:
            raise AzureDiTransientError(f"server_error: {exc}") from exc
        if status == 429:
            raise AzureDiTransientError(f"rate_limited: {exc}") from exc
        raise AzureDiPermanentError(f"client_error[{status}]: {exc}") from exc
    except AzureError as exc:
        raise AzureDiTransientError(f"azure_error: {exc}") from exc

    return _parse_analyze_result(result)
