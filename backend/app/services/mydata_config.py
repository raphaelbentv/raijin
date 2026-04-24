from __future__ import annotations

import json
import uuid

from raijin_shared.models.mydata import (
    MyDataConnector,
    MyDataConnectorKind,
    MyDataSubmission,
)
from raijin_shared.security import encrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class MyDataConfigError(Exception):
    pass


async def get_connector(
    session: AsyncSession, *, tenant_id: uuid.UUID
) -> MyDataConnector | None:
    return await session.scalar(
        select(MyDataConnector).where(MyDataConnector.tenant_id == tenant_id)
    )


async def upsert_connector(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    kind: MyDataConnectorKind,
    base_url: str,
    credentials: dict,
    issuer_vat_number: str | None,
    auto_submit: bool,
    is_active: bool,
) -> MyDataConnector:
    existing = await get_connector(session, tenant_id=tenant_id)
    payload = encrypt(json.dumps(credentials))

    if existing:
        existing.kind = kind
        existing.base_url = base_url
        existing.credentials_encrypted = payload
        existing.issuer_vat_number = issuer_vat_number
        existing.auto_submit = auto_submit
        existing.is_active = is_active
        await session.commit()
        await session.refresh(existing)
        return existing

    connector = MyDataConnector(
        tenant_id=tenant_id,
        kind=kind,
        base_url=base_url,
        credentials_encrypted=payload,
        issuer_vat_number=issuer_vat_number,
        auto_submit=auto_submit,
        is_active=is_active,
    )
    session.add(connector)
    await session.commit()
    await session.refresh(connector)
    return connector


async def delete_connector(session: AsyncSession, *, connector: MyDataConnector) -> None:
    connector.is_active = False
    await session.commit()


async def get_submission(
    session: AsyncSession, *, tenant_id: uuid.UUID, invoice_id: uuid.UUID
) -> MyDataSubmission | None:
    submission = await session.scalar(
        select(MyDataSubmission).where(
            MyDataSubmission.tenant_id == tenant_id,
            MyDataSubmission.invoice_id == invoice_id,
        )
    )
    return submission
