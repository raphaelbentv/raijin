from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from raijin_shared.models.email_source import EmailProvider, EmailSource
from raijin_shared.security import decrypt, encrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class EmailSourceError(Exception):
    pass


class EmailSourceNotFoundError(EmailSourceError):
    pass


def _expires_at(expires_in_seconds: int | None) -> datetime | None:
    if not expires_in_seconds:
        return None
    return datetime.now(UTC) + timedelta(seconds=expires_in_seconds - 60)


async def upsert_email_source(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    provider: EmailProvider,
    account_email: str,
    access_token: str,
    refresh_token: str | None,
    expires_in: int | None,
) -> EmailSource:
    existing = await session.scalar(
        select(EmailSource).where(
            EmailSource.tenant_id == tenant_id,
            EmailSource.provider == provider,
            EmailSource.account_email == account_email,
        )
    )
    token_enc = encrypt(access_token)
    refresh_enc = encrypt(refresh_token) if refresh_token else None
    expires_at = _expires_at(expires_in)

    if existing:
        existing.access_token_encrypted = token_enc
        if refresh_enc:
            existing.refresh_token_encrypted = refresh_enc
        existing.token_expires_at = expires_at
        existing.is_active = True
        existing.last_error = None
        await session.commit()
        await session.refresh(existing)
        return existing

    source = EmailSource(
        tenant_id=tenant_id,
        provider=provider,
        account_email=account_email,
        access_token_encrypted=token_enc,
        refresh_token_encrypted=refresh_enc,
        token_expires_at=expires_at,
    )
    session.add(source)
    await session.commit()
    await session.refresh(source)
    return source


async def upsert_outlook_source(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    account_email: str,
    access_token: str,
    refresh_token: str | None,
    expires_in: int | None,
) -> EmailSource:
    return await upsert_email_source(
        session,
        tenant_id=tenant_id,
        provider=EmailProvider.OUTLOOK,
        account_email=account_email,
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
    )


async def upsert_gmail_source(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    account_email: str,
    access_token: str,
    refresh_token: str | None,
    expires_in: int | None,
) -> EmailSource:
    return await upsert_email_source(
        session,
        tenant_id=tenant_id,
        provider=EmailProvider.GMAIL,
        account_email=account_email,
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
    )


async def list_sources(
    session: AsyncSession, *, tenant_id: uuid.UUID
) -> list[EmailSource]:
    result = await session.scalars(
        select(EmailSource)
        .where(EmailSource.tenant_id == tenant_id)
        .order_by(EmailSource.created_at.desc())
    )
    return list(result.all())


async def get_source(
    session: AsyncSession, *, tenant_id: uuid.UUID, source_id: uuid.UUID
) -> EmailSource | None:
    source = await session.get(EmailSource, source_id)
    if source is None or source.tenant_id != tenant_id:
        return None
    return source


async def disconnect_source(
    session: AsyncSession, *, source: EmailSource
) -> None:
    source.is_active = False
    source.access_token_encrypted = ""
    source.refresh_token_encrypted = None
    await session.commit()


def decrypt_access_token(source: EmailSource) -> str:
    return decrypt(source.access_token_encrypted)


def decrypt_refresh_token(source: EmailSource) -> str | None:
    if not source.refresh_token_encrypted:
        return None
    return decrypt(source.refresh_token_encrypted)


def is_access_token_expired(source: EmailSource) -> bool:
    if source.token_expires_at is None:
        return False
    return datetime.now(UTC) >= source.token_expires_at
