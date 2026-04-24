from __future__ import annotations

import json
import uuid

from raijin_shared.models.erp import ErpConnector, ErpConnectorKind, ErpExport
from raijin_shared.security import encrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def get_connector(
    session: AsyncSession, *, tenant_id: uuid.UUID
) -> ErpConnector | None:
    return await session.scalar(
        select(ErpConnector).where(ErpConnector.tenant_id == tenant_id)
    )


async def upsert_connector(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    kind: ErpConnectorKind,
    base_url: str,
    credentials: dict,
    config: dict | None,
    auto_export: bool,
    is_active: bool,
) -> ErpConnector:
    existing = await get_connector(session, tenant_id=tenant_id)
    payload = encrypt(json.dumps(credentials))

    if existing:
        existing.kind = kind
        existing.base_url = base_url
        existing.credentials_encrypted = payload
        existing.config = config
        existing.auto_export = auto_export
        existing.is_active = is_active
        await session.commit()
        await session.refresh(existing)
        return existing

    connector = ErpConnector(
        tenant_id=tenant_id,
        kind=kind,
        base_url=base_url,
        credentials_encrypted=payload,
        config=config,
        auto_export=auto_export,
        is_active=is_active,
    )
    session.add(connector)
    await session.commit()
    await session.refresh(connector)
    return connector


async def delete_connector(session: AsyncSession, *, connector: ErpConnector) -> None:
    connector.is_active = False
    await session.commit()


async def get_export(
    session: AsyncSession, *, tenant_id: uuid.UUID, invoice_id: uuid.UUID
) -> ErpExport | None:
    return await session.scalar(
        select(ErpExport).where(
            ErpExport.tenant_id == tenant_id,
            ErpExport.invoice_id == invoice_id,
        )
    )
