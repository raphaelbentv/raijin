from decimal import Decimal

from raijin_shared.validation import (
    ValidationReport,
    validate_confidence,
    validate_required_fields,
    validate_totals,
)


def test_totals_consistent_no_issue() -> None:
    report = ValidationReport()
    validate_totals(Decimal("100"), Decimal("24"), Decimal("124"), report)
    assert report.issues == []


def test_totals_tolerance() -> None:
    report = ValidationReport()
    validate_totals(Decimal("100.00"), Decimal("24.00"), Decimal("124.01"), report)
    assert report.issues == []


def test_totals_mismatch_flags_error() -> None:
    report = ValidationReport()
    validate_totals(Decimal("100"), Decimal("24"), Decimal("200"), report)
    assert report.has_errors
    assert any(i.code == "totals_mismatch" for i in report.issues)


def test_subtotal_greater_than_total_flags_error() -> None:
    report = ValidationReport()
    validate_totals(Decimal("150"), Decimal("24"), Decimal("124"), report)
    assert any(i.code in ("subtotal_gt_total", "totals_mismatch") for i in report.issues)


def test_missing_total_flags_error() -> None:
    report = ValidationReport()
    validate_totals(Decimal("100"), Decimal("24"), None, report)
    assert report.has_errors


def test_confidence_high_no_warning() -> None:
    report = ValidationReport()
    validate_confidence(0.95, report)
    assert report.issues == []


def test_confidence_medium_is_warning() -> None:
    report = ValidationReport()
    validate_confidence(0.85, report)
    assert not report.has_errors
    assert any(i.code == "medium_confidence" for i in report.issues)


def test_confidence_low_is_error() -> None:
    report = ValidationReport()
    validate_confidence(0.60, report)
    assert report.has_errors


def test_confidence_missing_is_warning() -> None:
    report = ValidationReport()
    validate_confidence(None, report)
    assert not report.has_errors
    assert any(i.code == "no_confidence" for i in report.issues)


def test_required_fields_ok() -> None:
    from datetime import date

    report = ValidationReport()
    validate_required_fields("Acme Corp", "INV-1", date(2026, 1, 1), report)
    assert report.issues == []


def test_required_fields_all_missing() -> None:
    report = ValidationReport()
    validate_required_fields(None, None, None, report)
    codes = {i.code for i in report.issues}
    assert {"missing_vendor_name", "missing_invoice_id", "missing_invoice_date"} <= codes
