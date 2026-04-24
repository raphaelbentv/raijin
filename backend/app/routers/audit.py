from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict, field_validator
from raijin_shared.models.audit import AuditLog
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbSession
from app.core.permissions import RequireReviewer

router = APIRouter(prefix="/audit", tags=["audit"], dependencies=[RequireReviewer])


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID | None
    action: str
    entity_type: str
    entity_id: uuid.UUID | None
    before_state: dict | None
    after_state: dict | None
    ip_address: str | None
    user_agent: str | None
    created_at: datetime

    @field_validator("ip_address", mode="before")
    @classmethod
    def _ip_to_str(cls, v):
        return str(v) if v is not None else None


class AuditLogListResponse(BaseModel):
    items: list[AuditLogOut]
    total: int
    page: int
    page_size: int


@router.get("", response_model=AuditLogListResponse)
async def list_audit(
    db: DbSession,
    user: CurrentUser,
    action: Annotated[str | None, Query()] = None,
    entity_type: Annotated[str | None, Query()] = None,
    entity_id: Annotated[uuid.UUID | None, Query()] = None,
    date_from: Annotated[datetime | None, Query(alias="from")] = None,
    date_to: Annotated[datetime | None, Query(alias="to")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> AuditLogListResponse:
    filters = [AuditLog.tenant_id == user.tenant_id]
    if action:
        filters.append(AuditLog.action == action)
    if entity_type:
        filters.append(AuditLog.entity_type == entity_type)
    if entity_id:
        filters.append(AuditLog.entity_id == entity_id)
    if date_from:
        filters.append(AuditLog.created_at >= date_from)
    if date_to:
        filters.append(AuditLog.created_at <= date_to)

    total = await db.scalar(select(func.count(AuditLog.id)).where(*filters)) or 0

    result = await db.scalars(
        select(AuditLog)
        .where(*filters)
        .order_by(AuditLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return AuditLogListResponse(
        items=[AuditLogOut.model_validate(i) for i in result.all()],
        total=total,
        page=page,
        page_size=page_size,
    )
