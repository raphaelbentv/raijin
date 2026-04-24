"""Orchestration de l'export ERP pour une facture validée."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from raijin_shared.erp.epsilon_mapper import (
    EpsilonMappingError,
    map_invoice_to_epsilon,
)
from raijin_shared.erp.softone_mapper import (
    SoftOneMappingError,
    map_invoice_to_softone,
)
from raijin_shared.models.erp import (
    ErpConnector,
    ErpConnectorKind,
    ErpExport,
    ErpExportStatus,
)
from raijin_shared.models.invoice import Invoice
from raijin_shared.models.notification import NotificationKind
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.logging import get_logger
from app.services.erp import ErpPermanentError, build_erp_connector
from app.services.notification import create_notification

logger = get_logger("raijin.erp")


class ConnectorMissingError(Exception):
    pass


def _load_invoice(session: Session, invoice_id: uuid.UUID) -> Invoice | None:
    return session.scalar(
        select(Invoice)
        .options(selectinload(Invoice.lines), selectinload(Invoice.supplier))
        .where(Invoice.id == invoice_id)
    )


def _get_or_create_export(
    session: Session, *, tenant_id: uuid.UUID, invoice_id: uuid.UUID
) -> ErpExport:
    export = session.scalar(
        select(ErpExport).where(ErpExport.invoice_id == invoice_id)
    )
    if export is None:
        export = ErpExport(tenant_id=tenant_id, invoice_id=invoice_id)
        session.add(export)
        session.flush()
    return export


def export_invoice_to_erp(session: Session, invoice_id: uuid.UUID) -> ErpExport:
    invoice = _load_invoice(session, invoice_id)
    if invoice is None:
        raise ErpPermanentError("invoice_not_found")

    connector_row = session.scalar(
        select(ErpConnector).where(
            ErpConnector.tenant_id == invoice.tenant_id,
            ErpConnector.is_active.is_(True),
        )
    )
    if connector_row is None:
        raise ConnectorMissingError("no_active_connector")

    export = _get_or_create_export(
        session, tenant_id=invoice.tenant_id, invoice_id=invoice.id
    )
    export.connector_id = connector_row.id
    export.retry_count += 1

    connector = build_erp_connector(connector_row)

    # Résolution du fournisseur (optionnelle, best-effort)
    supplier_external_id: str | None = None
    if invoice.supplier and invoice.supplier.vat_number:
        try:
            supplier_external_id = connector.find_supplier_by_vat(
                invoice.supplier.vat_number
            )
        except Exception as exc:
            logger.warning(
                "erp.supplier_lookup_failed",
                invoice_id=str(invoice_id),
                error=str(exc),
            )

    if connector_row.kind == ErpConnectorKind.SOFTONE:
        try:
            payload = map_invoice_to_softone(
                invoice, trdr_external_id=supplier_external_id
            )
        except SoftOneMappingError as exc:
            export.status = ErpExportStatus.FAILED
            export.error_message = f"mapping: {exc}"
            session.commit()
            raise ErpPermanentError(f"mapping: {exc}") from exc
    elif connector_row.kind == ErpConnectorKind.EPSILON_NET:
        try:
            payload = map_invoice_to_epsilon(
                invoice, supplier_external_id=supplier_external_id
            )
        except EpsilonMappingError as exc:
            export.status = ErpExportStatus.FAILED
            export.error_message = f"mapping: {exc}"
            session.commit()
            raise ErpPermanentError(f"mapping: {exc}") from exc
    else:
        raise ErpPermanentError(f"unsupported_kind:{connector_row.kind}")

    export.payload = payload
    export.submitted_at = datetime.now(UTC)
    logger.info(
        "erp.export.start",
        invoice_id=str(invoice_id),
        connector=connector_row.kind.value,
    )

    result = connector.export_invoice(payload)
    export.external_id = result.external_id
    export.response_body = result.raw_response

    if result.success:
        export.status = (
            ErpExportStatus.ACKNOWLEDGED
            if result.external_id
            else ErpExportStatus.SUBMITTED
        )
        export.acknowledged_at = (
            datetime.now(UTC) if result.external_id else None
        )
        export.error_message = None
        create_notification(
            session,
            tenant_id=invoice.tenant_id,
            kind=NotificationKind.ERP_EXPORTED,
            title="Facture exportée vers l'ERP",
            body=(
                f"{invoice.source_file_name} · ID {result.external_id}"
                if result.external_id
                else f"{invoice.source_file_name} · accepté"
            ),
            entity_type="invoice",
            entity_id=invoice.id,
        )
    else:
        export.status = ErpExportStatus.FAILED
        export.error_message = (result.raw_response or "rejected")[:1000]
        create_notification(
            session,
            tenant_id=invoice.tenant_id,
            kind=NotificationKind.INTEGRATION_ERROR,
            title="Échec export ERP",
            body=f"{invoice.source_file_name} — {(result.raw_response or 'rejet')[:180]}",
            entity_type="invoice",
            entity_id=invoice.id,
        )

    session.commit()
    logger.info(
        "erp.export.done",
        invoice_id=str(invoice_id),
        status=export.status.value,
        external_id=export.external_id,
    )
    return export


def mark_export_failed(session: Session, invoice_id: uuid.UUID, reason: str) -> None:
    export = session.scalar(
        select(ErpExport).where(ErpExport.invoice_id == invoice_id)
    )
    if export is None:
        return
    export.status = ErpExportStatus.FAILED
    export.error_message = reason[:1000]
    session.commit()
