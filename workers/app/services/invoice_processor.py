from __future__ import annotations

import re
import uuid
from decimal import Decimal
from difflib import SequenceMatcher

from raijin_shared.models.invoice import Invoice, InvoiceLine, InvoiceStatus
from raijin_shared.models.notification import NotificationKind
from raijin_shared.models.supplier import Supplier
from raijin_shared.validation import (
    ValidationReport,
    validate_confidence,
    validate_dates,
    validate_duplicate,
    validate_required_fields,
    validate_totals,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.core.storage import download_object
from app.services.azure_di import ExtractedInvoice, analyze_invoice_bytes
from app.services.normalizer import (
    parse_amount,
    parse_currency,
    parse_date,
    parse_vat_id,
    parse_vat_rate,
)
from app.services.notification import create_notification

logger = get_logger("raijin.ocr")


class InvoiceNotFoundError(Exception):
    pass


class InvoiceNotProcessableError(Exception):
    pass


def _normalize_invoice_number(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]", "", (value or "").lower())


def _invoice_number_score(left: str | None, right: str | None) -> float:
    left_norm = _normalize_invoice_number(left)
    right_norm = _normalize_invoice_number(right)
    if not left_norm or not right_norm:
        return 0.0
    if left_norm == right_norm:
        return 1.0
    return SequenceMatcher(None, left_norm, right_norm).ratio()


def _flag_possible_duplicate(session: Session, invoice: Invoice) -> uuid.UUID | None:
    invoice.possible_duplicate_of_id = None
    invoice.duplicate_score = None
    invoice.duplicate_reason = None

    if not invoice.invoice_number or not invoice.supplier_id or invoice.total_ttc is None:
        return None

    tolerance = Decimal("1.00")
    candidates = session.scalars(
        select(Invoice).where(
            Invoice.tenant_id == invoice.tenant_id,
            Invoice.supplier_id == invoice.supplier_id,
            Invoice.id != invoice.id,
            Invoice.total_ttc >= invoice.total_ttc - tolerance,
            Invoice.total_ttc <= invoice.total_ttc + tolerance,
            Invoice.status != InvoiceStatus.FAILED,
        )
    ).all()

    best: tuple[Invoice, float] | None = None
    for candidate in candidates:
        score = _invoice_number_score(invoice.invoice_number, candidate.invoice_number)
        if score < 0.78:
            continue
        if best is None or score > best[1]:
            best = (candidate, score)

    if best is None:
        return None

    candidate, score = best
    invoice.possible_duplicate_of_id = candidate.id
    invoice.duplicate_score = Decimal(str(round(score, 4)))
    invoice.duplicate_reason = "supplier+total+invoice_number_fuzzy"
    return candidate.id


def _resolve_supplier(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    extracted: ExtractedInvoice,
) -> Supplier | None:
    vat = parse_vat_id(extracted.vendor_tax_id)
    name = (extracted.vendor_name or "").strip() or None

    if vat:
        supplier = session.scalar(
            select(Supplier).where(Supplier.tenant_id == tenant_id, Supplier.vat_number == vat)
        )
        if supplier:
            return supplier

    if name:
        supplier = session.scalar(
            select(Supplier).where(Supplier.tenant_id == tenant_id, Supplier.name == name)
        )
        if supplier:
            if vat and not supplier.vat_number:
                supplier.vat_number = vat
            return supplier

    if not name and not vat:
        return None

    supplier = Supplier(
        tenant_id=tenant_id,
        name=name or "Fournisseur inconnu",
        vat_number=vat,
        country_code=vat[:2] if vat else None,
        address_line1=extracted.vendor_address,
    )
    session.add(supplier)
    session.flush()
    return supplier


def _apply_lines(session: Session, invoice: Invoice, extracted: ExtractedInvoice) -> None:
    for existing in list(invoice.lines):
        session.delete(existing)
    session.flush()

    for extracted_line in extracted.lines:
        line = InvoiceLine(
            invoice_id=invoice.id,
            line_number=extracted_line.line_number,
            description=extracted_line.description,
            quantity=extracted_line.quantity,
            unit_price=extracted_line.unit_price,
            vat_rate=extracted_line.vat_rate,
            line_total_ht=extracted_line.line_total_ht,
            line_total_ttc=extracted_line.line_total_ttc,
        )
        session.add(line)


def _apply_extraction(
    invoice: Invoice,
    extracted: ExtractedInvoice,
    supplier: Supplier | None,
) -> None:
    invoice.supplier_id = supplier.id if supplier else None
    invoice.invoice_number = (extracted.invoice_id or "").strip() or None
    invoice.issue_date = parse_date(extracted.invoice_date)
    invoice.due_date = parse_date(extracted.due_date)
    invoice.currency = parse_currency(extracted.currency, default=invoice.currency or "EUR")
    invoice.total_ht = parse_amount(extracted.subtotal)
    invoice.total_vat = parse_amount(extracted.total_tax)
    invoice.total_ttc = parse_amount(extracted.invoice_total)
    invoice.ocr_raw = extracted.raw_payload or None
    invoice.ocr_confidence = (
        Decimal(str(extracted.overall_confidence)) if extracted.overall_confidence is not None else None
    )

    # taux TVA reformatés (les champs extraits côté lignes peuvent arriver en "24%")
    for line in invoice.lines:
        if line.vat_rate is not None:
            rate = parse_vat_rate(str(line.vat_rate))
            if rate is not None:
                line.vat_rate = rate


def process_invoice_ocr(session: Session, invoice_id: uuid.UUID) -> Invoice:
    """Exécute le pipeline OCR complet sur une facture.

    Appelé depuis une tâche Celery. Transactionnel via session_scope du caller.
    """
    invoice = session.get(Invoice, invoice_id)
    if invoice is None:
        raise InvoiceNotFoundError(str(invoice_id))

    if invoice.status not in (InvoiceStatus.UPLOADED, InvoiceStatus.PROCESSING, InvoiceStatus.FAILED):
        raise InvoiceNotProcessableError(
            f"invoice {invoice_id} has status {invoice.status.value}"
        )

    logger.info("ocr.started", invoice_id=str(invoice_id), file_key=invoice.source_file_key)
    invoice.status = InvoiceStatus.PROCESSING
    session.flush()

    data = download_object(invoice.source_file_key)
    extracted = analyze_invoice_bytes(data)

    supplier = _resolve_supplier(session, tenant_id=invoice.tenant_id, extracted=extracted)
    _apply_lines(session, invoice, extracted)
    _apply_extraction(invoice, extracted, supplier)

    duplicate_id = _flag_possible_duplicate(session, invoice)

    report = ValidationReport()
    validate_required_fields(
        vendor_name=extracted.vendor_name,
        invoice_id=extracted.invoice_id,
        invoice_date=invoice.issue_date,
        report=report,
    )
    validate_totals(
        subtotal=invoice.total_ht,
        total_tax=invoice.total_vat,
        invoice_total=invoice.total_ttc,
        report=report,
    )
    validate_dates(issue_date=invoice.issue_date, due_date=invoice.due_date, report=report)
    validate_duplicate(duplicate_id is not None, duplicate_id, report)
    validate_confidence(overall=extracted.overall_confidence, report=report)

    invoice.validation_errors = report.to_dict() if report.issues else None
    invoice.status = InvoiceStatus.READY_FOR_REVIEW
    session.flush()

    supplier_label = supplier.name if supplier else "fournisseur inconnu"
    create_notification(
        session,
        tenant_id=invoice.tenant_id,
        kind=NotificationKind.INVOICE_READY,
        title="Nouvelle facture à valider",
        body=f"{invoice.source_file_name} — {supplier_label}",
        entity_type="invoice",
        entity_id=invoice.id,
    )

    logger.info(
        "ocr.completed",
        invoice_id=str(invoice_id),
        confidence=extracted.overall_confidence,
        issues=len(report.issues),
    )
    return invoice


def mark_invoice_failed(session: Session, invoice_id: uuid.UUID, reason: str) -> None:
    invoice = session.get(Invoice, invoice_id)
    if invoice is None:
        return
    invoice.status = InvoiceStatus.FAILED
    invoice.rejected_reason = reason[:500]
    invoice.validation_errors = {"issues": [{"code": "ocr_failed", "severity": "error", "message": reason[:500]}]}
    session.flush()

    create_notification(
        session,
        tenant_id=invoice.tenant_id,
        kind=NotificationKind.INVOICE_FAILED,
        title="Échec OCR",
        body=f"{invoice.source_file_name} — {reason[:200]}",
        entity_type="invoice",
        entity_id=invoice.id,
    )

    logger.error("ocr.failed", invoice_id=str(invoice_id), reason=reason)
