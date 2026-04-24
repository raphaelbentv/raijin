import contextlib
import hashlib
import re
import uuid
from datetime import date
from decimal import Decimal
from difflib import SequenceMatcher
from io import BytesIO

from raijin_shared.models.correction import InvoiceCorrection
from raijin_shared.models.invoice import Invoice, InvoiceLine, InvoiceStatus
from raijin_shared.models.notification import NotificationKind
from raijin_shared.models.user import User
from raijin_shared.validation import (
    ValidationReport,
    validate_dates,
    validate_duplicate,
    validate_required_fields,
    validate_totals,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.celery_client import enqueue_invoice_ocr
from app.core.config import get_settings
from app.core.storage import build_object_key, put_object
from app.services.notification import create_notification


class InvoiceError(Exception):
    pass


class FileTooLargeError(InvoiceError):
    pass


class UnsupportedMimeError(InvoiceError):
    pass


class DuplicateInvoiceError(InvoiceError):
    def __init__(self, existing_id: uuid.UUID) -> None:
        super().__init__("duplicate_invoice")
        self.existing_id = existing_id


class InvalidTransitionError(InvoiceError):
    def __init__(self, current: InvoiceStatus, attempted: str) -> None:
        super().__init__(f"cannot_{attempted}_from_{current.value}")
        self.current = current
        self.attempted = attempted


class InvoiceHasErrorsError(InvoiceError):
    pass


async def upload_invoice(
    session: AsyncSession,
    *,
    uploader: User,
    filename: str,
    content_type: str,
    data: bytes,
) -> Invoice:
    settings = get_settings()

    if content_type not in settings.allowed_mime_set:
        raise UnsupportedMimeError(content_type)

    if len(data) > settings.upload_max_size_bytes:
        raise FileTooLargeError()

    if len(data) == 0:
        raise UnsupportedMimeError("empty_file")

    checksum = hashlib.sha256(data).hexdigest()

    duplicate = await session.scalar(
        select(Invoice).where(
            Invoice.tenant_id == uploader.tenant_id,
            Invoice.source_file_checksum == checksum,
        )
    )
    if duplicate:
        raise DuplicateInvoiceError(duplicate.id)

    key = build_object_key(uploader.tenant_id, filename)
    put_object(
        key=key,
        body=BytesIO(data),
        content_type=content_type,
        metadata={
            "tenant_id": str(uploader.tenant_id),
            "uploader_user_id": str(uploader.id),
            "original_filename": filename[:200],
        },
    )

    invoice = Invoice(
        tenant_id=uploader.tenant_id,
        uploader_user_id=uploader.id,
        status=InvoiceStatus.UPLOADED,
        source_file_key=key,
        source_file_mime=content_type,
        source_file_size=len(data),
        source_file_checksum=checksum,
        source_file_name=filename[:255],
    )
    session.add(invoice)
    await session.commit()
    await session.refresh(invoice)

    # l'enqueue ne doit jamais faire échouer l'upload — le fichier est déjà persisté
    with contextlib.suppress(Exception):
        enqueue_invoice_ocr(str(invoice.id))

    return invoice


async def list_invoices(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    status: InvoiceStatus | None = None,
    q: str | None = None,
    supplier_id: uuid.UUID | None = None,
    issue_from: date | None = None,
    issue_to: date | None = None,
    amount_min: Decimal | None = None,
    amount_max: Decimal | None = None,
    tag: str | None = None,
    category_id: uuid.UUID | None = None,
    paid: bool | None = None,
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[Invoice], int]:
    page = max(1, page)
    page_size = min(max(1, page_size), 100)

    filters = [Invoice.tenant_id == tenant_id]
    if status is not None:
        filters.append(Invoice.status == status)
    if q:
        like = f"%{q.strip()}%"
        filters.append(
            (Invoice.invoice_number.ilike(like)) | (Invoice.source_file_name.ilike(like))
        )
    if supplier_id:
        filters.append(Invoice.supplier_id == supplier_id)
    if issue_from:
        filters.append(Invoice.issue_date >= issue_from)
    if issue_to:
        filters.append(Invoice.issue_date <= issue_to)
    if amount_min is not None:
        filters.append(Invoice.total_ttc >= amount_min)
    if amount_max is not None:
        filters.append(Invoice.total_ttc <= amount_max)
    if tag:
        filters.append(Invoice.tags.contains([tag]))
    if category_id:
        filters.append(Invoice.category_id == category_id)
    if paid is not None:
        filters.append(Invoice.paid_at.is_not(None) if paid else Invoice.paid_at.is_(None))

    total = await session.scalar(
        select(func.count(Invoice.id)).where(*filters)
    ) or 0

    result = await session.scalars(
        select(Invoice)
        .where(*filters)
        .order_by(Invoice.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(result.all()), total


async def get_invoice(
    session: AsyncSession, *, tenant_id: uuid.UUID, invoice_id: uuid.UUID
) -> Invoice | None:
    invoice = await session.get(Invoice, invoice_id)
    if invoice is None or invoice.tenant_id != tenant_id:
        return None
    await session.refresh(invoice, attribute_names=["lines", "supplier"])
    return invoice


_EDITABLE_STATUSES = {InvoiceStatus.READY_FOR_REVIEW, InvoiceStatus.REJECTED}


def _revalidate(invoice: Invoice) -> None:
    report = ValidationReport()
    vendor_name = invoice.supplier.name if invoice.supplier else None
    validate_required_fields(
        vendor_name=vendor_name,
        invoice_id=invoice.invoice_number,
        invoice_date=invoice.issue_date,
        report=report,
    )
    validate_totals(
        subtotal=invoice.total_ht,
        total_tax=invoice.total_vat,
        invoice_total=invoice.total_ttc,
        report=report,
    )
    validate_dates(
        issue_date=invoice.issue_date, due_date=invoice.due_date, report=report
    )
    validate_duplicate(
        invoice.possible_duplicate_of_id is not None,
        invoice.possible_duplicate_of_id,
        report,
    )
    invoice.validation_errors = report.to_dict() if report.issues else None


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


async def flag_possible_duplicate(session: AsyncSession, invoice: Invoice) -> None:
    invoice.possible_duplicate_of_id = None
    invoice.duplicate_score = None
    invoice.duplicate_reason = None

    if not invoice.supplier_id or not invoice.invoice_number or invoice.total_ttc is None:
        return

    tolerance = Decimal("1.00")
    candidates = await session.scalars(
        select(Invoice)
        .where(
            Invoice.tenant_id == invoice.tenant_id,
            Invoice.id != invoice.id,
            Invoice.supplier_id == invoice.supplier_id,
            Invoice.total_ttc >= invoice.total_ttc - tolerance,
            Invoice.total_ttc <= invoice.total_ttc + tolerance,
            Invoice.status != InvoiceStatus.FAILED,
        )
        .order_by(Invoice.created_at.desc())
        .limit(50)
    )

    best: tuple[Invoice, float] | None = None
    for candidate in candidates.all():
        score = _invoice_number_score(invoice.invoice_number, candidate.invoice_number)
        if score < 0.78:
            continue
        if best is None or score > best[1]:
            best = (candidate, score)

    if best is None:
        return

    candidate, score = best
    invoice.possible_duplicate_of_id = candidate.id
    invoice.duplicate_score = Decimal(str(round(score, 4)))
    invoice.duplicate_reason = "supplier+total+invoice_number_fuzzy"


def _apply_patch_lines(invoice: Invoice, patched_lines: list) -> None:
    invoice.lines.clear()
    for line_patch in sorted(patched_lines, key=lambda x: x.line_number):
        invoice.lines.append(
            InvoiceLine(
                line_number=line_patch.line_number,
                description=line_patch.description,
                quantity=line_patch.quantity,
                unit_price=line_patch.unit_price,
                vat_rate=line_patch.vat_rate,
                line_total_ht=line_patch.line_total_ht,
                line_total_ttc=line_patch.line_total_ttc,
            )
        )


_TRACKED_FIELDS = (
    "invoice_number",
    "issue_date",
    "due_date",
    "currency",
    "total_ht",
    "total_vat",
    "total_ttc",
    "supplier_id",
    "paid_at",
    "payment_method",
    "payment_reference",
    "category_id",
    "tags",
    "custom_fields",
)


def _record_corrections(
    session: AsyncSession,
    *,
    invoice: Invoice,
    user: User,
    before: dict[str, object],
) -> None:
    for field_name in _TRACKED_FIELDS:
        old_value = before.get(field_name)
        new_value = getattr(invoice, field_name)
        if old_value == new_value:
            continue
        session.add(
            InvoiceCorrection(
                tenant_id=invoice.tenant_id,
                invoice_id=invoice.id,
                user_id=user.id,
                field=field_name,
                before_value=str(old_value) if old_value is not None else None,
                after_value=str(new_value) if new_value is not None else None,
            )
        )


async def update_invoice(
    session: AsyncSession,
    *,
    invoice: Invoice,
    patch,
    user: User,
) -> Invoice:
    if invoice.status not in _EDITABLE_STATUSES:
        raise InvalidTransitionError(invoice.status, "edit")

    before = {f: getattr(invoice, f) for f in _TRACKED_FIELDS}

    update_fields = patch.model_dump(exclude_unset=True, exclude={"lines"})
    for field_name, value in update_fields.items():
        setattr(invoice, field_name, value)

    if patch.lines is not None:
        _apply_patch_lines(invoice, patch.lines)

    if invoice.status == InvoiceStatus.REJECTED:
        invoice.status = InvoiceStatus.READY_FOR_REVIEW
        invoice.rejected_reason = None

    _record_corrections(session, invoice=invoice, user=user, before=before)

    await session.flush()
    await session.refresh(invoice, attribute_names=["lines", "supplier"])
    await flag_possible_duplicate(session, invoice)
    _revalidate(invoice)
    await session.commit()
    await session.refresh(invoice)
    await session.refresh(invoice, attribute_names=["lines", "supplier"])
    return invoice


async def invoice_stats(
    session: AsyncSession, *, tenant_id: uuid.UUID
) -> dict[str, int]:
    result = await session.execute(
        select(Invoice.status, func.count(Invoice.id))
        .where(Invoice.tenant_id == tenant_id)
        .group_by(Invoice.status)
    )
    counters: dict[str, int] = {s.value: 0 for s in InvoiceStatus}
    total = 0
    for status_value, count in result.all():
        key = status_value.value if hasattr(status_value, "value") else str(status_value)
        counters[key] = count
        total += count
    counters["total"] = total
    return counters


async def list_corrections(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    invoice_id: uuid.UUID,
) -> list[InvoiceCorrection]:
    result = await session.scalars(
        select(InvoiceCorrection)
        .where(
            InvoiceCorrection.tenant_id == tenant_id,
            InvoiceCorrection.invoice_id == invoice_id,
        )
        .order_by(InvoiceCorrection.created_at.desc())
    )
    return list(result.all())


async def confirm_invoice(session: AsyncSession, invoice: Invoice) -> Invoice:
    if invoice.status != InvoiceStatus.READY_FOR_REVIEW:
        raise InvalidTransitionError(invoice.status, "confirm")

    _revalidate(invoice)
    if invoice.validation_errors and any(
        i.get("severity") == "error" for i in invoice.validation_errors.get("issues", [])
    ):
        raise InvoiceHasErrorsError()

    invoice.status = InvoiceStatus.CONFIRMED
    invoice.confirmed_at = date.today()
    invoice.rejected_reason = None

    supplier_label = invoice.supplier.name if invoice.supplier else "fournisseur inconnu"
    await create_notification(
        session,
        tenant_id=invoice.tenant_id,
        kind=NotificationKind.INVOICE_READY,
        title="Facture validée",
        body=f"{invoice.source_file_name} — {supplier_label}",
        entity_type="invoice",
        entity_id=invoice.id,
    )

    await session.commit()
    await session.refresh(invoice)
    await session.refresh(invoice, attribute_names=["lines", "supplier"])

    await _maybe_enqueue_mydata(session, invoice)
    await _maybe_enqueue_erp(session, invoice)

    return invoice


async def _maybe_enqueue_mydata(session: AsyncSession, invoice: Invoice) -> None:
    """Après confirm, enqueue la soumission myDATA si auto_submit est actif."""
    from raijin_shared.models.mydata import MyDataConnector as ConnectorModel

    connector = await session.scalar(
        select(ConnectorModel).where(
            ConnectorModel.tenant_id == invoice.tenant_id,
            ConnectorModel.is_active.is_(True),
            ConnectorModel.auto_submit.is_(True),
        )
    )
    if connector is None:
        return

    try:
        from app.core.celery_client import get_celery

        get_celery().send_task("mydata.submit_invoice", args=[str(invoice.id)])
    except Exception:
        # enqueue fail ne doit jamais casser le confirm
        pass


async def _maybe_enqueue_erp(session: AsyncSession, invoice: Invoice) -> None:
    """Après confirm, enqueue l'export ERP si auto_export est actif."""
    from raijin_shared.models.erp import ErpConnector as ErpConnectorModel

    connector = await session.scalar(
        select(ErpConnectorModel).where(
            ErpConnectorModel.tenant_id == invoice.tenant_id,
            ErpConnectorModel.is_active.is_(True),
            ErpConnectorModel.auto_export.is_(True),
        )
    )
    if connector is None:
        return

    try:
        from app.core.celery_client import get_celery

        get_celery().send_task("erp.export_invoice", args=[str(invoice.id)])
    except Exception:
        pass


async def reject_invoice(session: AsyncSession, invoice: Invoice, reason: str) -> Invoice:
    if invoice.status not in (InvoiceStatus.READY_FOR_REVIEW, InvoiceStatus.PROCESSING):
        raise InvalidTransitionError(invoice.status, "reject")

    invoice.status = InvoiceStatus.REJECTED
    invoice.rejected_reason = reason[:500]

    await create_notification(
        session,
        tenant_id=invoice.tenant_id,
        kind=NotificationKind.INVOICE_FAILED,
        title="Facture rejetée",
        body=f"{invoice.source_file_name} — {reason[:120]}",
        entity_type="invoice",
        entity_id=invoice.id,
    )

    await session.commit()
    await session.refresh(invoice)
    await session.refresh(invoice, attribute_names=["lines", "supplier"])
    return invoice


async def skip_invoice(session: AsyncSession, invoice: Invoice) -> Invoice:
    if invoice.status != InvoiceStatus.READY_FOR_REVIEW:
        raise InvalidTransitionError(invoice.status, "skip")
    # no-op on status — on bump juste updated_at via un flush
    await session.flush()
    await session.commit()
    await session.refresh(invoice)
    await session.refresh(invoice, attribute_names=["lines", "supplier"])
    return invoice


async def reopen_invoice(session: AsyncSession, invoice: Invoice) -> Invoice:
    if invoice.status not in (InvoiceStatus.CONFIRMED, InvoiceStatus.REJECTED):
        raise InvalidTransitionError(invoice.status, "reopen")
    invoice.status = InvoiceStatus.READY_FOR_REVIEW
    invoice.confirmed_at = None
    invoice.rejected_reason = None

    await create_notification(
        session,
        tenant_id=invoice.tenant_id,
        kind=NotificationKind.SYSTEM,
        title="Facture réouverte",
        body=f"{invoice.source_file_name} est de nouveau modifiable.",
        entity_type="invoice",
        entity_id=invoice.id,
    )

    await session.commit()
    await session.refresh(invoice)
    await session.refresh(invoice, attribute_names=["lines", "supplier"])
    return invoice
