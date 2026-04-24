from __future__ import annotations

import uuid

from raijin_shared.models.cloud_drive import CloudDriveProvider, CloudDriveSource
from raijin_shared.models.email_source import EmailProvider, EmailSource
from sqlalchemy import select

from app.celery_app import celery_app
from app.core.database import session_scope
from app.core.logging import get_logger
from app.services.gdrive_client import DriveAuthError, DriveError
from app.services.gdrive_ingest import sync_gdrive_source
from app.services.gmail_client import GmailAuthError, GmailError
from app.services.gmail_ingest import sync_gmail_source

logger = get_logger("raijin.tasks.google")


@celery_app.task(
    name="email.sync_gmail",
    bind=True,
    autoretry_for=(GmailError,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=3,
    acks_late=True,
)
def sync_gmail_task(self, source_id: str) -> dict:
    source_uuid = uuid.UUID(source_id)
    logger.info("task.gmail.sync", source_id=source_id, attempt=self.request.retries + 1)
    try:
        with session_scope() as session:
            source = session.get(EmailSource, source_uuid)
            if source is None or source.provider != EmailProvider.GMAIL:
                return {"status": "not_found"}
            if not source.is_active:
                return {"status": "inactive"}
            try:
                result = sync_gmail_source(session, source)
                return {"status": "ok", **result.to_dict()}
            except GmailAuthError as exc:
                source.last_error = f"auth_failed: {exc}"[:1000]
                source.is_active = False
                session.add(source)
                session.commit()
                return {"status": "auth_failed", "error": str(exc)}
    except GmailError as exc:
        with session_scope() as session:
            source = session.get(EmailSource, source_uuid)
            if source:
                source.last_error = str(exc)[:1000]
                session.add(source)
                session.commit()
        raise


@celery_app.task(
    name="drive.sync_gdrive",
    bind=True,
    autoretry_for=(DriveError,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=3,
    acks_late=True,
)
def sync_gdrive_task(self, source_id: str) -> dict:
    source_uuid = uuid.UUID(source_id)
    logger.info("task.gdrive.sync", source_id=source_id, attempt=self.request.retries + 1)
    try:
        with session_scope() as session:
            source = session.get(CloudDriveSource, source_uuid)
            if source is None or source.provider != CloudDriveProvider.GDRIVE:
                return {"status": "not_found"}
            if not source.is_active:
                return {"status": "inactive"}
            try:
                result = sync_gdrive_source(session, source)
                return {"status": "ok", **result.to_dict()}
            except DriveAuthError as exc:
                source.last_error = f"auth_failed: {exc}"[:1000]
                source.is_active = False
                session.add(source)
                session.commit()
                return {"status": "auth_failed", "error": str(exc)}
    except DriveError as exc:
        with session_scope() as session:
            source = session.get(CloudDriveSource, source_uuid)
            if source:
                source.last_error = str(exc)[:1000]
                session.add(source)
                session.commit()
        raise


@celery_app.task(name="email.sync_all_gmail")
def sync_all_gmail() -> dict:
    triggered = 0
    with session_scope() as session:
        ids = session.scalars(
            select(EmailSource.id).where(
                EmailSource.provider == EmailProvider.GMAIL,
                EmailSource.is_active.is_(True),
            )
        )
        for sid in ids.all():
            celery_app.send_task("email.sync_gmail", args=[str(sid)])
            triggered += 1
    return {"triggered": triggered}


@celery_app.task(name="drive.sync_all_gdrive")
def sync_all_gdrive() -> dict:
    triggered = 0
    with session_scope() as session:
        ids = session.scalars(
            select(CloudDriveSource.id).where(
                CloudDriveSource.provider == CloudDriveProvider.GDRIVE,
                CloudDriveSource.is_active.is_(True),
            )
        )
        for sid in ids.all():
            celery_app.send_task("drive.sync_gdrive", args=[str(sid)])
            triggered += 1
    return {"triggered": triggered}
