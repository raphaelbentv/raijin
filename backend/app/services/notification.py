"""Helper async pour créer des Notifications depuis le backend (routes)."""
from __future__ import annotations

import uuid

from raijin_shared.models.notification import Notification, NotificationKind
from raijin_shared.models.user import User
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.email_delivery import send_transactional_email


async def create_notification(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    kind: NotificationKind,
    title: str,
    body: str | None = None,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    commit: bool = False,
) -> Notification:
    target_user = await session.get(User, user_id) if user_id else None
    preferences = target_user.notification_preferences if target_user else None
    kind_prefs = (preferences or {}).get(kind.value, {}) if isinstance(preferences, dict) else {}
    in_app_enabled = kind_prefs.get("in_app", True)
    email_enabled = kind_prefs.get("email", False)

    notif = Notification(
        tenant_id=tenant_id,
        user_id=user_id,
        kind=kind,
        title=title,
        body=body,
        entity_type=entity_type,
        entity_id=entity_id,
    )
    if in_app_enabled:
        session.add(notif)
    if commit:
        await session.commit()
    else:
        await session.flush()
    if email_enabled and target_user:
        await send_transactional_email(
            to_email=target_user.email,
            subject=f"Raijin — {title}",
            text=f"{title}\n\n{body or ''}",
            html=f"<p><strong>{title}</strong></p><p>{body or ''}</p>",
        )
    return notif
