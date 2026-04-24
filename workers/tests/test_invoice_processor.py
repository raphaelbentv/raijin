from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from app.services import invoice_processor as ip
from app.services.azure_di import ExtractedInvoice, ExtractedLine
from raijin_shared.validation import ValidationReport


def _fake_invoice(status_uploaded: bool = True):
    invoice = MagicMock()
    invoice.id = uuid.uuid4()
    invoice.tenant_id = uuid.uuid4()
    invoice.source_file_key = "tenants/x/invoices/2026/04/sample.pdf"
    invoice.currency = "EUR"
    invoice.lines = []
    invoice.status = (
        type(  # dynamic Enum substitute
            "S", (), {"UPLOADED": "uploaded", "PROCESSING": "processing", "FAILED": "failed"}
        ).UPLOADED
        if status_uploaded
        else "confirmed"
    )
    return invoice


def test_apply_extraction_maps_fields() -> None:
    invoice = MagicMock()
    invoice.currency = "EUR"
    invoice.lines = []

    extracted = ExtractedInvoice(
        vendor_name="Acme Corp",
        vendor_tax_id="EL123456789",
        invoice_id="INV-001",
        invoice_date="2026-04-21",
        due_date="21/05/2026",
        currency="EUR",
        subtotal=Decimal("100.00"),
        total_tax=Decimal("24.00"),
        invoice_total=Decimal("124.00"),
        overall_confidence=0.95,
    )
    supplier = MagicMock()
    supplier.id = uuid.uuid4()

    ip._apply_extraction(invoice, extracted, supplier)

    assert invoice.supplier_id == supplier.id
    assert invoice.invoice_number == "INV-001"
    assert invoice.issue_date == date(2026, 4, 21)
    assert invoice.due_date == date(2026, 5, 21)
    assert invoice.currency == "EUR"
    assert invoice.total_ht == Decimal("100.00")
    assert invoice.total_vat == Decimal("24.00")
    assert invoice.total_ttc == Decimal("124.00")
    assert invoice.ocr_confidence == Decimal("0.95")


def test_apply_extraction_handles_missing_values() -> None:
    invoice = MagicMock()
    invoice.currency = "EUR"
    invoice.lines = []

    extracted = ExtractedInvoice(
        vendor_name=None,
        invoice_id=None,
        invoice_date=None,
    )
    ip._apply_extraction(invoice, extracted, None)

    assert invoice.supplier_id is None
    assert invoice.invoice_number is None
    assert invoice.issue_date is None
    assert invoice.total_ttc is None
    assert invoice.ocr_confidence is None


def test_validation_report_flags_inconsistent_totals() -> None:
    from raijin_shared.validation import validate_totals

    r = ValidationReport()
    validate_totals(Decimal("100"), Decimal("24"), Decimal("200"), r)
    assert r.has_errors
