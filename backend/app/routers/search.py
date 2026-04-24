from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict
from raijin_shared.models.invoice import Invoice, InvoiceStatus
from raijin_shared.models.supplier import Supplier
from sqlalchemy import or_, select

from app.api.deps import CurrentUser, DbSession

router = APIRouter(prefix="/search", tags=["search"])


class InvoiceHit(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_file_name: str
    invoice_number: str | None
    status: InvoiceStatus


class SupplierHit(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    vat_number: str | None
    country_code: str | None


class SearchResponse(BaseModel):
    invoices: list[InvoiceHit]
    suppliers: list[SupplierHit]


@router.get("", response_model=SearchResponse)
async def search(
    db: DbSession,
    user: CurrentUser,
    q: Annotated[str, Query(min_length=1, max_length=80)],
    limit: Annotated[int, Query(ge=1, le=20)] = 6,
) -> SearchResponse:
    like = f"%{q}%"

    invoice_stmt = (
        select(Invoice)
        .where(
            Invoice.tenant_id == user.tenant_id,
            or_(
                Invoice.source_file_name.ilike(like),
                Invoice.invoice_number.ilike(like),
            ),
        )
        .order_by(Invoice.created_at.desc())
        .limit(limit)
    )
    invoices = (await db.scalars(invoice_stmt)).all()

    supplier_stmt = (
        select(Supplier)
        .where(
            Supplier.tenant_id == user.tenant_id,
            or_(
                Supplier.name.ilike(like),
                Supplier.vat_number.ilike(like),
            ),
        )
        .order_by(Supplier.name.asc())
        .limit(limit)
    )
    suppliers = (await db.scalars(supplier_stmt)).all()

    return SearchResponse(
        invoices=[InvoiceHit.model_validate(i) for i in invoices],
        suppliers=[SupplierHit.model_validate(s) for s in suppliers],
    )
