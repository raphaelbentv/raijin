from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from raijin_shared.models.email_source import EmailSource
from raijin_shared.models.notification import NotificationKind
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.services import graph_client as gc
from app.services.ingest import ingest_file
from app.services.notification import create_notification

logger = get_logger("raijin.outlook")


@dataclass
class SyncResult:
    source_id: uuid.UUID
    messages_seen: int = 0
    attachments_ingested: int = 0
    attachments_duplicated: int = 0
    errors: list[str] | None = None

    def to_dict(self) -> dict:
        return {
            "source_id": str(self.source_id),
            "messages_seen": self.messages_seen,
            "attachments_ingested": self.attachments_ingested,
            "attachments_duplicated": self.attachments_duplicated,
            "errors": self.errors or [],
        }


def sync_outlook_source(session: Session, source: EmailSource) -> SyncResult:
    if not source.is_active:
        raise gc.GraphError("source_inactive")

    result = SyncResult(source_id=source.id, errors=[])
    since = source.last_sync_at
    newest_received: datetime | None = None

    for message in gc.list_messages_with_attachments(session, source, since=since):
        result.messages_seen += 1
        message_id = message["id"]
        received_str = message.get("receivedDateTime")
        received = _parse_iso(received_str) if received_str else None
        if received and (newest_received is None or received > newest_received):
            newest_received = received

        try:
            attachments = gc.list_message_attachments(session, source, message_id)
        except gc.GraphError as exc:
            result.errors.append(f"{message_id}: {exc}")
            continue

        for attachment in attachments:
            if not gc.is_supported_attachment(attachment):
                continue
            filename = attachment.get("name") or f"email-{message_id}.bin"
            mime = gc.attachment_mime(attachment)
            try:
                data = gc.download_attachment_bytes(attachment)
            except gc.GraphError as exc:
                result.errors.append(f"{message_id}/{filename}: {exc}")
                continue

            invoice = ingest_file(
                session,
                tenant_id=source.tenant_id,
                filename=filename,
                content_type=mime,
                data=data,
                source="email",
                source_metadata={
                    "email_message_id": message_id,
                    "email_from": _extract_from(message),
                    "email_subject": (message.get("subject") or "")[:200],
                    "email_received_at": received_str or "",
                    "email_source_id": str(source.id),
                },
            )
            if invoice is None:
                result.attachments_duplicated += 1
            else:
                result.attachments_ingested += 1

    # Update source
    source.last_sync_at = newest_received or datetime.now(UTC)
    source.last_error = None
    session.add(source)

    if result.attachments_ingested > 0:
        create_notification(
            session,
            tenant_id=source.tenant_id,
            kind=NotificationKind.INTEGRATION_SYNCED,
            title="Outlook synchronisé",
            body=f"{result.attachments_ingested} pièce(s) jointe(s) ingérée(s) depuis {source.account_email}.",
            entity_type="email_source",
            entity_id=source.id,
        )
    session.commit()

    logger.info(
        "outlook.sync.done",
        source_id=str(source.id),
        **result.to_dict(),
    )
    return result


def _parse_iso(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)


def _extract_from(message: dict) -> str:
    from_field = message.get("from") or {}
    email_addr = from_field.get("emailAddress") or {}
    return email_addr.get("address", "")[:255]
