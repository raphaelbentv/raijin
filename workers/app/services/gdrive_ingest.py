from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from raijin_shared.models.cloud_drive import CloudDriveSource
from raijin_shared.models.notification import NotificationKind
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.services import gdrive_client as gc
from app.services.ingest import ingest_file
from app.services.notification import create_notification

logger = get_logger("raijin.gdrive")


@dataclass
class SyncResult:
    source_id: uuid.UUID
    files_seen: int = 0
    files_ingested: int = 0
    files_duplicated: int = 0
    errors: list[str] | None = None

    def to_dict(self) -> dict:
        return {
            "source_id": str(self.source_id),
            "files_seen": self.files_seen,
            "files_ingested": self.files_ingested,
            "files_duplicated": self.files_duplicated,
            "errors": self.errors or [],
        }


def _parse_modified(value: str) -> datetime | None:
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def sync_gdrive_source(session: Session, source: CloudDriveSource) -> SyncResult:
    result = SyncResult(source_id=source.id, errors=[])
    since = source.last_sync_at
    newest: datetime | None = None

    for f in gc.list_files_in_folder(session, source, since=since):
        result.files_seen += 1
        modified = _parse_modified(f.get("modifiedTime", ""))
        if modified and (newest is None or modified > newest):
            newest = modified

        try:
            data = gc.download_file(session, source, f["id"])
        except gc.DriveError as exc:
            result.errors.append(f"{f.get('name', '?')}: {exc}")
            continue

        invoice = ingest_file(
            session,
            tenant_id=source.tenant_id,
            filename=f.get("name", f["id"]),
            content_type=f.get("mimeType", "application/octet-stream"),
            data=data,
            source="drive",
            source_metadata={
                "drive_file_id": f["id"],
                "drive_folder_id": source.folder_id,
                "drive_source_id": str(source.id),
                "drive_modified_at": f.get("modifiedTime", ""),
            },
        )
        if invoice is None:
            result.files_duplicated += 1
        else:
            result.files_ingested += 1

    source.last_sync_at = newest or datetime.now(UTC)
    source.last_error = None
    session.add(source)

    if result.files_ingested > 0:
        create_notification(
            session,
            tenant_id=source.tenant_id,
            kind=NotificationKind.INTEGRATION_SYNCED,
            title="Google Drive synchronisé",
            body=f"{result.files_ingested} fichier(s) ingéré(s) depuis {source.folder_name or source.folder_id}.",
            entity_type="cloud_drive_source",
            entity_id=source.id,
        )
    session.commit()

    logger.info("gdrive.sync.done", source_id=str(source.id), **result.to_dict())
    return result
