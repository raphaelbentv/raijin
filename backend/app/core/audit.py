"""Helper central pour écrire des AuditLog."""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import Request
from raijin_shared.models.audit import AuditLog
from raijin_shared.models.user import User
from sqlalchemy.ext.asyncio import AsyncSession


def _request_context(request: Request | None) -> tuple[str | None, str | None]:
    if request is None:
        return None, None
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    return ip, (ua[:500] if ua else None)


async def log_action(
    session: AsyncSession,
    *,
    user: User,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    request: Request | None = None,
) -> None:
    ip, ua = _request_context(request)
    session.add(
        AuditLog(
            tenant_id=user.tenant_id,
            user_id=user.id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            before_state=before,
            after_state=after,
            ip_address=ip,
            user_agent=ua,
        )
    )
    await session.commit()
