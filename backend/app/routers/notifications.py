from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from raijin_shared.models.notification import Notification, NotificationKind
from sqlalchemy import func, select, update

from app.api.deps import CurrentUser, DbSession

router = APIRouter(prefix="/notifications", tags=["notifications"])


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: NotificationKind
    title: str
    body: str | None
    entity_type: str | None
    entity_id: uuid.UUID | None
    is_read: bool
    created_at: datetime


class NotificationListResponse(BaseModel):
    items: list[NotificationOut]
    total: int
    unread: int


@router.get("", response_model=NotificationListResponse)
async def list_notifications(
    db: DbSession,
    user: CurrentUser,
    unread_only: Annotated[bool, Query()] = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> NotificationListResponse:
    filters = [Notification.tenant_id == user.tenant_id]
    if unread_only:
        filters.append(Notification.is_read.is_(False))

    total = await db.scalar(
        select(func.count(Notification.id)).where(Notification.tenant_id == user.tenant_id)
    ) or 0
    unread = await db.scalar(
        select(func.count(Notification.id)).where(
            Notification.tenant_id == user.tenant_id, Notification.is_read.is_(False)
        )
    ) or 0

    result = await db.scalars(
        select(Notification)
        .where(*filters)
        .order_by(Notification.created_at.desc())
        .limit(limit)
    )
    return NotificationListResponse(
        items=[NotificationOut.model_validate(n) for n in result.all()],
        total=total,
        unread=unread,
    )


@router.post("/{notification_id}/read", status_code=204)
async def mark_read(
    notification_id: uuid.UUID, db: DbSession, user: CurrentUser
) -> None:
    n = await db.scalar(
        select(Notification).where(
            Notification.tenant_id == user.tenant_id,
            Notification.id == notification_id,
        )
    )
    if n is None:
        raise HTTPException(status_code=404, detail="notification_not_found")
    n.is_read = True
    await db.commit()


@router.post("/read-all", status_code=204)
async def mark_all_read(db: DbSession, user: CurrentUser) -> None:
    await db.execute(
        update(Notification)
        .where(Notification.tenant_id == user.tenant_id, Notification.is_read.is_(False))
        .values(is_read=True)
    )
    await db.commit()
