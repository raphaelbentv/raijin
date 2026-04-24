from __future__ import annotations

import uuid

from raijin_shared.models.email_source import EmailProvider, EmailSource
from sqlalchemy import select

from app.celery_app import celery_app
from app.core.database import session_scope
from app.core.logging import get_logger
from app.services.graph_client import GraphAuthError, GraphError
from app.services.outlook_ingest import sync_outlook_source

logger = get_logger("raijin.tasks.email")


@celery_app.task(
    name="email.sync_outlook",
    bind=True,
    autoretry_for=(GraphError,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=3,
    acks_late=True,
)
def sync_outlook_task(self, source_id: str) -> dict:
    source_uuid = uuid.UUID(source_id)
    logger.info("task.email.sync.start", source_id=source_id, attempt=self.request.retries + 1)

    try:
        with session_scope() as session:
            source = session.get(EmailSource, source_uuid)
            if source is None:
                return {"status": "not_found"}
            if not source.is_active:
                return {"status": "inactive"}

            try:
                result = sync_outlook_source(session, source)
                return {"status": "ok", **result.to_dict()}
            except GraphAuthError as exc:
                source.last_error = f"auth_failed: {exc}"[:1000]
                source.is_active = False
                session.add(source)
                session.commit()
                logger.error("task.email.auth_error", source_id=source_id, error=str(exc))
                return {"status": "auth_failed", "error": str(exc)}
    except GraphError as exc:
        with session_scope() as session:
            source = session.get(EmailSource, source_uuid)
            if source:
                source.last_error = str(exc)[:1000]
                session.add(source)
                session.commit()
        raise


@celery_app.task(name="email.sync_all_outlook")
def sync_all_outlook() -> dict:
    """Scheduler : enqueue un sync par EmailSource Outlook active."""
    triggered = 0
    with session_scope() as session:
        sources = session.scalars(
            select(EmailSource.id).where(
                EmailSource.provider == EmailProvider.OUTLOOK,
                EmailSource.is_active.is_(True),
            )
        )
        for source_id in sources.all():
            celery_app.send_task("email.sync_outlook", args=[str(source_id)])
            triggered += 1

    logger.info("scheduler.email.sync_all_outlook", triggered=triggered)
    return {"triggered": triggered}
