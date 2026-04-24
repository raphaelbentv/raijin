"""Ingest un fichier de facture (depuis email, drive, etc.) en Invoice DB + S3.

Centralise la logique partagée entre les différentes sources d'ingestion.
"""
from __future__ import annotations

import hashlib
import uuid
from typing import Literal

from raijin_shared.models.invoice import Invoice, InvoiceStatus
from raijin_shared.models.user import User, UserRole
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.celery_app import celery_app
from app.core.logging import get_logger
from app.core.storage import build_object_key, put_object

logger = get_logger("raijin.ingest")

IngestionSource = Literal["manual", "email", "drive"]

SUPPORTED_MIME = {"application/pdf", "image/jpeg", "image/jpg", "image/png"}


class IngestError(Exception):
    pass


class DuplicateIngestError(IngestError):
    def __init__(self, existing_id: uuid.UUID) -> None:
        super().__init__("duplicate")
        self.existing_id = existing_id


def _find_tenant_uploader(session: Session, tenant_id: uuid.UUID) -> User:
    user = session.scalar(
        select(User)
        .where(User.tenant_id == tenant_id, User.is_active.is_(True))
        .order_by(User.role == UserRole.ADMIN, User.created_at.asc())
        .limit(1)
    )
    if user is None:
        raise IngestError("no_active_user_for_tenant")
    return user


def ingest_file(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    filename: str,
    content_type: str,
    data: bytes,
    source: IngestionSource = "email",
    source_metadata: dict[str, str] | None = None,
) -> Invoice | None:
    """Crée une Invoice depuis un fichier. Retourne None si doublon silencieux."""
    mime = content_type.lower().split(";")[0].strip()
    if mime not in SUPPORTED_MIME:
        logger.warning("ingest.unsupported_mime", mime=mime, filename=filename)
        return None

    if not data:
        return None

    checksum = hashlib.sha256(data).hexdigest()
    duplicate = session.scalar(
        select(Invoice).where(
            Invoice.tenant_id == tenant_id,
            Invoice.source_file_checksum == checksum,
        )
    )
    if duplicate:
        logger.info(
            "ingest.duplicate",
            tenant_id=str(tenant_id),
            existing_id=str(duplicate.id),
            source=source,
        )
        return None

    uploader = _find_tenant_uploader(session, tenant_id)
    key = build_object_key(tenant_id, filename)
    metadata = {
        "tenant_id": str(tenant_id),
        "uploader_user_id": str(uploader.id),
        "source": source,
        "original_filename": filename[:200],
    }
    if source_metadata:
        metadata.update({k: str(v)[:200] for k, v in source_metadata.items()})

    put_object(key=key, body=data, content_type=mime, metadata=metadata)

    invoice = Invoice(
        tenant_id=tenant_id,
        uploader_user_id=uploader.id,
        status=InvoiceStatus.UPLOADED,
        source_file_key=key,
        source_file_mime=mime,
        source_file_size=len(data),
        source_file_checksum=checksum,
        source_file_name=filename[:255],
    )
    session.add(invoice)
    session.flush()
    session.commit()

    logger.info(
        "ingest.success",
        tenant_id=str(tenant_id),
        invoice_id=str(invoice.id),
        source=source,
        bytes=len(data),
    )

    celery_app.send_task("invoice.process_ocr", args=[str(invoice.id)])
    return invoice
