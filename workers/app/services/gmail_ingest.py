from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from raijin_shared.models.email_source import EmailSource
from raijin_shared.models.notification import NotificationKind
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.services import gmail_client as gc
from app.services.ingest import ingest_file
from app.services.notification import create_notification

logger = get_logger("raijin.gmail")


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


def sync_gmail_source(session: Session, source: EmailSource) -> SyncResult:
    result = SyncResult(source_id=source.id, errors=[])
    since = source.last_sync_at
    newest = since or datetime.now(UTC)

    for summary in gc.list_messages_with_attachments(session, source, since=since):
        result.messages_seen += 1
        try:
            message = gc.get_message(session, source, summary["id"])
        except gc.GmailError as exc:
            result.errors.append(f"{summary['id']}: {exc}")
            continue

        meta = gc.extract_message_meta(message)
        for attachment_id, filename, mime in gc.iter_attachments(message):
            try:
                data = gc.download_attachment(
                    session, source, summary["id"], attachment_id
                )
            except gc.GmailError as exc:
                result.errors.append(f"{summary['id']}/{filename}: {exc}")
                continue

            invoice = ingest_file(
                session,
                tenant_id=source.tenant_id,
                filename=filename,
                content_type=mime,
                data=data,
                source="email",
                source_metadata={
                    "email_provider": "gmail",
                    "email_message_id": summary["id"],
                    "email_from": meta.get("from", ""),
                    "email_subject": meta.get("subject", ""),
                    "email_source_id": str(source.id),
                },
            )
            if invoice is None:
                result.attachments_duplicated += 1
            else:
                result.attachments_ingested += 1

    source.last_sync_at = newest
    source.last_error = None
    session.add(source)

    if result.attachments_ingested > 0:
        create_notification(
            session,
            tenant_id=source.tenant_id,
            kind=NotificationKind.INTEGRATION_SYNCED,
            title="Gmail synchronisé",
            body=f"{result.attachments_ingested} pièce(s) jointe(s) ingérée(s) depuis {source.account_email}.",
            entity_type="email_source",
            entity_id=source.id,
        )
    session.commit()

    logger.info("gmail.sync.done", source_id=str(source.id), **result.to_dict())
    return result
