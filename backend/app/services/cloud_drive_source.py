from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from raijin_shared.models.cloud_drive import CloudDriveProvider, CloudDriveSource
from raijin_shared.security import encrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


def _expires_at(seconds: int | None) -> datetime | None:
    if not seconds:
        return None
    return datetime.now(UTC) + timedelta(seconds=seconds - 60)


async def upsert_gdrive_source(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    account_email: str | None,
    folder_id: str,
    folder_name: str | None,
    access_token: str,
    refresh_token: str | None,
    expires_in: int | None,
) -> CloudDriveSource:
    existing = await session.scalar(
        select(CloudDriveSource).where(
            CloudDriveSource.tenant_id == tenant_id,
            CloudDriveSource.provider == CloudDriveProvider.GDRIVE,
            CloudDriveSource.folder_id == folder_id,
        )
    )
    token_enc = encrypt(access_token)
    refresh_enc = encrypt(refresh_token) if refresh_token else None
    expires = _expires_at(expires_in)

    if existing:
        existing.account_email = account_email or existing.account_email
        existing.folder_name = folder_name or existing.folder_name
        existing.access_token_encrypted = token_enc
        if refresh_enc:
            existing.refresh_token_encrypted = refresh_enc
        existing.token_expires_at = expires
        existing.is_active = True
        existing.last_error = None
        await session.commit()
        await session.refresh(existing)
        return existing

    source = CloudDriveSource(
        tenant_id=tenant_id,
        provider=CloudDriveProvider.GDRIVE,
        account_email=account_email,
        folder_id=folder_id,
        folder_name=folder_name,
        access_token_encrypted=token_enc,
        refresh_token_encrypted=refresh_enc,
        token_expires_at=expires,
    )
    session.add(source)
    await session.commit()
    await session.refresh(source)
    return source


async def list_gdrive_sources(
    session: AsyncSession, *, tenant_id: uuid.UUID
) -> list[CloudDriveSource]:
    result = await session.scalars(
        select(CloudDriveSource)
        .where(CloudDriveSource.tenant_id == tenant_id)
        .order_by(CloudDriveSource.created_at.desc())
    )
    return list(result.all())


async def get_gdrive_source(
    session: AsyncSession, *, tenant_id: uuid.UUID, source_id: uuid.UUID
) -> CloudDriveSource | None:
    source = await session.get(CloudDriveSource, source_id)
    if source is None or source.tenant_id != tenant_id:
        return None
    return source


async def disconnect_gdrive_source(
    session: AsyncSession, *, source: CloudDriveSource
) -> None:
    source.is_active = False
    source.access_token_encrypted = ""
    source.refresh_token_encrypted = None
    await session.commit()
