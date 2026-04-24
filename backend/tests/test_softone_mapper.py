from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

from raijin_shared.erp.softone_mapper import map_invoice_to_softone


def _make_invoice_with_lines():
    invoice = MagicMock()
    invoice.issue_date = date(2026, 4, 21)
    invoice.due_date = date(2026, 5, 21)
    invoice.invoice_number = "INV-001"
    invoice.currency = "EUR"
    invoice.total_ht = Decimal("100.00")
    invoice.total_vat = Decimal("24.00")
    invoice.total_ttc = Decimal("124.00")
    invoice.source_file_name = "facture.pdf"

    line = MagicMock()
    line.description = "Consulting"
    line.quantity = Decimal("1")
    line.unit_price = Decimal("100.00")
    line.vat_rate = Decimal("0.24")
    line.line_total_ht = Decimal("100.00")
    line.line_total_ttc = Decimal("124.00")
    invoice.lines = [line]
    return invoice


def test_map_with_lines_produces_findoc_and_itelines():
    invoice = _make_invoice_with_lines()
    payload = map_invoice_to_softone(invoice, trdr_external_id=1234)
    assert "FINDOC" in payload and "ITELINES" in payload
    assert payload["FINDOC"][0]["SERIES"] == 1000
    assert payload["FINDOC"][0]["FINCODE"] == "INV-001"
    assert payload["FINDOC"][0]["TRNDATE"] == "2026-04-21"
    assert payload["FINDOC"][0]["GRAMNT"] == 124.00
    assert payload["FINDOC"][0]["TRDR"] == 1234
    assert len(payload["ITELINES"]) == 1
    assert payload["ITELINES"][0]["VATRTE"] == 24


def test_map_without_lines_infers_single_line():
    invoice = _make_invoice_with_lines()
    invoice.lines = []
    payload = map_invoice_to_softone(invoice)
    assert len(payload["ITELINES"]) == 1
    assert payload["ITELINES"][0]["VATRTE"] == 24


def test_map_requires_issue_date():
    invoice = _make_invoice_with_lines()
    invoice.issue_date = None
    import pytest

    with pytest.raises(ValueError):
        map_invoice_to_softone(invoice)
