"""Helper sync pour créer des Notifications depuis les workers Celery."""
from __future__ import annotations

import uuid

from raijin_shared.models.notification import Notification, NotificationKind
from sqlalchemy.orm import Session


def create_notification(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    kind: NotificationKind,
    title: str,
    body: str | None = None,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
) -> Notification:
    notif = Notification(
        tenant_id=tenant_id,
        user_id=user_id,
        kind=kind,
        title=title,
        body=body,
        entity_type=entity_type,
        entity_id=entity_id,
    )
    session.add(notif)
    session.flush()
    return notif
