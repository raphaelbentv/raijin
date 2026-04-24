from datetime import date
from decimal import Decimal

from raijin_shared.mydata.xml_builder import (
    InvoiceData,
    InvoiceLineData,
    Party,
    build_invoices_doc_xml,
    vat_category_from_rate,
)


def test_vat_category_standard_rate() -> None:
    assert vat_category_from_rate(Decimal("0.24")) == 1


def test_vat_category_reduced_rate() -> None:
    assert vat_category_from_rate(Decimal("0.13")) == 2


def test_vat_category_super_reduced_rate() -> None:
    assert vat_category_from_rate(Decimal("0.06")) == 3


def test_vat_category_zero_rate() -> None:
    assert vat_category_from_rate(Decimal("0")) == 7
    assert vat_category_from_rate(Decimal("0.00")) == 7


def test_build_simple_invoice_xml_has_expected_elements() -> None:
    invoice = InvoiceData(
        series="A",
        number="101",
        issue_date=date(2026, 4, 21),
        currency="EUR",
        issuer=Party(vat_number="123456789"),
        counterpart=Party(vat_number="987654321", name="Acme SA"),
        lines=[
            InvoiceLineData(
                line_number=1,
                net_value=Decimal("100.00"),
                vat_category=1,
                vat_amount=Decimal("24.00"),
                description="Consulting",
            )
        ],
        total_net=Decimal("100.00"),
        total_vat=Decimal("24.00"),
        total_gross=Decimal("124.00"),
    )

    xml = build_invoices_doc_xml([invoice]).decode("utf-8")

    assert "<?xml version" in xml
    assert "InvoicesDoc" in xml
    assert "<ns0:issuer" in xml or ":issuer" in xml
    assert "123456789" in xml
    assert "987654321" in xml
    assert "100.00" in xml
    assert "124.00" in xml
    assert "<ns0:invoiceHeader" in xml or "invoiceHeader" in xml
    assert "2026-04-21" in xml


def test_build_multi_invoice_xml() -> None:
    invoices = [
        InvoiceData(
            series="A",
            number=str(i),
            issue_date=date(2026, 4, 21),
            issuer=Party(vat_number="123456789"),
            counterpart=Party(vat_number="987654321"),
            lines=[
                InvoiceLineData(
                    line_number=1,
                    net_value=Decimal("10.00"),
                    vat_category=1,
                    vat_amount=Decimal("2.40"),
                )
            ],
            total_net=Decimal("10.00"),
            total_vat=Decimal("2.40"),
            total_gross=Decimal("12.40"),
        )
        for i in (1, 2, 3)
    ]
    xml = build_invoices_doc_xml(invoices).decode("utf-8")
    assert xml.count("<ns0:invoice>") >= 3 or xml.count(":invoice>") >= 3
