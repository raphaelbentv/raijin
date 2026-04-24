from raijin_shared.models.invoice import InvoiceStatus

from app.services.invoice import (
    _EDITABLE_STATUSES,
    _TRACKED_FIELDS,
    DuplicateInvoiceError,
    InvalidTransitionError,
    InvoiceHasErrorsError,
    _invoice_number_score,
)


def test_editable_statuses_limited_to_review_and_rejected() -> None:
    assert {InvoiceStatus.READY_FOR_REVIEW, InvoiceStatus.REJECTED} == _EDITABLE_STATUSES


def test_tracked_fields_include_critical() -> None:
    assert {
        "invoice_number",
        "issue_date",
        "due_date",
        "currency",
        "total_ht",
        "total_vat",
        "total_ttc",
        "supplier_id",
    } <= set(_TRACKED_FIELDS)


def test_invalid_transition_error_message() -> None:
    exc = InvalidTransitionError(InvoiceStatus.CONFIRMED, "edit")
    assert "cannot_edit_from_confirmed" in str(exc)


def test_duplicate_invoice_error_carries_id() -> None:
    import uuid

    eid = uuid.uuid4()
    exc = DuplicateInvoiceError(eid)
    assert exc.existing_id == eid


def test_invoice_has_errors_exists() -> None:
    assert InvoiceHasErrorsError is not None


def test_invoice_number_score_accepts_small_ocr_variants() -> None:
    assert _invoice_number_score("INV-2026-0007", "INV 2026 0007") == 1.0
    assert _invoice_number_score("INV-2026-0007", "INV-2026-0008") >= 0.78
    assert _invoice_number_score("INV-2026-0007", "CN-99") < 0.78
