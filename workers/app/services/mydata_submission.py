"""Orchestration de la soumission myDATA pour une facture."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from raijin_shared.models.invoice import Invoice
from raijin_shared.models.mydata import (
    MyDataConnector,
    MyDataSubmission,
    MyDataSubmissionStatus,
)
from raijin_shared.models.notification import NotificationKind
from raijin_shared.mydata.invoice_mapper import (
    InvoiceMappingError,
    map_invoice_to_mydata,
)
from raijin_shared.mydata.xml_builder import build_invoices_doc_xml
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.logging import get_logger
from app.services.mydata import MyDataPermanentError, build_connector
from app.services.notification import create_notification

logger = get_logger("raijin.mydata")


class ConnectorMissingError(Exception):
    pass


def _load_invoice(session: Session, invoice_id: uuid.UUID) -> Invoice | None:
    return session.scalar(
        select(Invoice)
        .options(selectinload(Invoice.lines), selectinload(Invoice.supplier))
        .where(Invoice.id == invoice_id)
    )


def _get_or_create_submission(
    session: Session, *, tenant_id: uuid.UUID, invoice_id: uuid.UUID
) -> MyDataSubmission:
    submission = session.scalar(
        select(MyDataSubmission).where(MyDataSubmission.invoice_id == invoice_id)
    )
    if submission is None:
        submission = MyDataSubmission(tenant_id=tenant_id, invoice_id=invoice_id)
        session.add(submission)
        session.flush()
    return submission


def submit_invoice_mydata(session: Session, invoice_id: uuid.UUID) -> MyDataSubmission:
    invoice = _load_invoice(session, invoice_id)
    if invoice is None:
        raise MyDataPermanentError("invoice_not_found")

    connector_row = session.scalar(
        select(MyDataConnector).where(
            MyDataConnector.tenant_id == invoice.tenant_id,
            MyDataConnector.is_active.is_(True),
        )
    )
    if connector_row is None:
        raise ConnectorMissingError("no_active_connector")

    submission = _get_or_create_submission(
        session, tenant_id=invoice.tenant_id, invoice_id=invoice.id
    )
    submission.connector_id = connector_row.id
    submission.retry_count += 1

    try:
        mapped = map_invoice_to_mydata(
            invoice, issuer_vat_number=connector_row.issuer_vat_number or ""
        )
    except InvoiceMappingError as exc:
        submission.status = MyDataSubmissionStatus.FAILED
        submission.error_message = f"mapping: {exc}"
        session.commit()
        raise MyDataPermanentError(f"mapping: {exc}") from exc

    xml_payload = build_invoices_doc_xml([mapped])
    submission.payload_xml = xml_payload.decode("utf-8")

    connector = build_connector(connector_row)
    submission.submitted_at = datetime.now(UTC)
    logger.info(
        "mydata.submit.start",
        invoice_id=str(invoice_id),
        connector=connector_row.kind.value,
    )

    result = connector.submit(xml_payload)
    submission.external_id = result.external_id
    submission.aade_mark = result.aade_mark
    submission.uid = result.uid
    submission.response_body = result.raw_response

    if result.success:
        submission.status = (
            MyDataSubmissionStatus.ACKNOWLEDGED
            if result.aade_mark
            else MyDataSubmissionStatus.SUBMITTED
        )
        submission.acknowledged_at = (
            datetime.now(UTC) if result.aade_mark else None
        )
        submission.error_message = None
        create_notification(
            session,
            tenant_id=invoice.tenant_id,
            kind=NotificationKind.MYDATA_SUBMITTED,
            title="myDATA soumis",
            body=(
                f"{invoice.source_file_name} · MARK AADE {submission.aade_mark}"
                if submission.aade_mark
                else f"{invoice.source_file_name} · en attente du MARK AADE"
            ),
            entity_type="invoice",
            entity_id=invoice.id,
        )
    else:
        submission.status = MyDataSubmissionStatus.FAILED
        submission.error_message = (result.raw_response or "rejected")[:1000]
        create_notification(
            session,
            tenant_id=invoice.tenant_id,
            kind=NotificationKind.INTEGRATION_ERROR,
            title="Échec soumission myDATA",
            body=f"{invoice.source_file_name} — {(result.raw_response or 'rejet')[:180]}",
            entity_type="invoice",
            entity_id=invoice.id,
        )

    session.commit()
    logger.info(
        "mydata.submit.done",
        invoice_id=str(invoice_id),
        status=submission.status.value,
        aade_mark=submission.aade_mark,
    )
    return submission


def mark_submission_failed(
    session: Session, invoice_id: uuid.UUID, reason: str
) -> None:
    submission = session.scalar(
        select(MyDataSubmission).where(MyDataSubmission.invoice_id == invoice_id)
    )
    if submission is None:
        return
    submission.status = MyDataSubmissionStatus.FAILED
    submission.error_message = reason[:1000]
    session.commit()
