import uuid
from datetime import datetime
from typing import Annotated

import sqlalchemy as sa
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from raijin_shared.models.invoice import Invoice
from raijin_shared.models.supplier import Supplier
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentUser, DbSession
from app.core.permissions import RequireReviewer

router = APIRouter(prefix="/suppliers", tags=["suppliers"])


class SupplierOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    vat_number: str | None
    country_code: str | None
    city: str | None
    email: str | None
    phone: str | None
    created_at: datetime


class SupplierMutation(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    vat_number: str | None = Field(default=None, max_length=32)
    country_code: str | None = Field(default=None, min_length=2, max_length=2)
    city: str | None = Field(default=None, max_length=100)
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=50)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        return value.strip()

    @field_validator("vat_number", "country_code", "city", "email", "phone", mode="before")
    @classmethod
    def blank_to_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = str(value).strip()
        return value or None

    @field_validator("country_code")
    @classmethod
    def normalize_country(cls, value: str | None) -> str | None:
        return value.upper() if value else None


class SupplierMergeRequest(BaseModel):
    source_supplier_id: uuid.UUID


class SupplierListItem(SupplierOut):
    invoice_count: int
    total_ttc: float | None


class SupplierListResponse(BaseModel):
    items: list[SupplierListItem]
    total: int
    page: int
    page_size: int


@router.get("", response_model=SupplierListResponse)
async def list_suppliers(
    db: DbSession,
    user: CurrentUser,
    search: Annotated[str | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> SupplierListResponse:
    base_filters = [Supplier.tenant_id == user.tenant_id]
    if search:
        like = f"%{search}%"
        base_filters.append(
            (Supplier.name.ilike(like)) | (Supplier.vat_number.ilike(like))
        )

    total = await db.scalar(select(func.count(Supplier.id)).where(*base_filters)) or 0

    stmt = (
        select(
            Supplier,
            func.count(Invoice.id).label("invoice_count"),
            func.coalesce(func.sum(Invoice.total_ttc), 0).label("total_ttc"),
        )
        .outerjoin(Invoice, Invoice.supplier_id == Supplier.id)
        .where(*base_filters)
        .group_by(Supplier.id)
        .order_by(func.count(Invoice.id).desc(), Supplier.name.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await db.execute(stmt)).all()

    items = [
        SupplierListItem(
            id=s.id,
            name=s.name,
            vat_number=s.vat_number,
            country_code=s.country_code,
            city=s.city,
            email=s.email,
            phone=s.phone,
            created_at=s.created_at,
            invoice_count=count,
            total_ttc=float(total_ttc) if total_ttc else 0.0,
        )
        for s, count, total_ttc in rows
    ]

    return SupplierListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post(
    "",
    response_model=SupplierOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[RequireReviewer],
)
async def create_supplier(
    body: SupplierMutation, db: DbSession, user: CurrentUser
) -> SupplierOut:
    supplier = Supplier(
        tenant_id=user.tenant_id,
        name=body.name,
        vat_number=body.vat_number,
        country_code=body.country_code,
        city=body.city,
        email=body.email,
        phone=body.phone,
    )
    db.add(supplier)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="supplier_vat_already_exists") from exc
    await db.refresh(supplier)
    return SupplierOut.model_validate(supplier)


@router.get("/{supplier_id}", response_model=SupplierOut)
async def get_supplier(
    supplier_id: uuid.UUID, db: DbSession, user: CurrentUser
) -> SupplierOut:
    s = await db.scalar(
        select(Supplier).where(
            Supplier.tenant_id == user.tenant_id, Supplier.id == supplier_id
        )
    )
    if s is None:
        raise HTTPException(status_code=404, detail="supplier_not_found")
    return SupplierOut.model_validate(s)


@router.patch("/{supplier_id}", response_model=SupplierOut, dependencies=[RequireReviewer])
async def update_supplier(
    supplier_id: uuid.UUID, body: SupplierMutation, db: DbSession, user: CurrentUser
) -> SupplierOut:
    supplier = await db.scalar(
        select(Supplier).where(
            Supplier.tenant_id == user.tenant_id, Supplier.id == supplier_id
        )
    )
    if supplier is None:
        raise HTTPException(status_code=404, detail="supplier_not_found")

    for field_name, value in body.model_dump().items():
        setattr(supplier, field_name, value)

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="supplier_vat_already_exists") from exc
    await db.refresh(supplier)
    return SupplierOut.model_validate(supplier)


@router.post(
    "/{supplier_id}/merge",
    response_model=SupplierOut,
    dependencies=[RequireReviewer],
)
async def merge_supplier(
    supplier_id: uuid.UUID,
    body: SupplierMergeRequest,
    db: DbSession,
    user: CurrentUser,
) -> SupplierOut:
    if supplier_id == body.source_supplier_id:
        raise HTTPException(status_code=400, detail="cannot_merge_same_supplier")

    target = await db.scalar(
        select(Supplier).where(
            Supplier.tenant_id == user.tenant_id, Supplier.id == supplier_id
        )
    )
    source = await db.scalar(
        select(Supplier).where(
            Supplier.tenant_id == user.tenant_id, Supplier.id == body.source_supplier_id
        )
    )
    if target is None or source is None:
        raise HTTPException(status_code=404, detail="supplier_not_found")

    await db.execute(
        update(Invoice)
        .where(Invoice.tenant_id == user.tenant_id, Invoice.supplier_id == source.id)
        .values(supplier_id=target.id)
    )
    await db.delete(source)
    await db.commit()
    await db.refresh(target)
    return SupplierOut.model_validate(target)


class SupplierInvoiceItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_file_name: str
    invoice_number: str | None
    issue_date: datetime | None
    total_ttc: float | None
    currency: str
    status: str


@router.get("/{supplier_id}/invoices", response_model=list[SupplierInvoiceItem])
async def list_supplier_invoices(
    supplier_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[SupplierInvoiceItem]:
    result = await db.scalars(
        select(Invoice)
        .where(
            Invoice.tenant_id == user.tenant_id, Invoice.supplier_id == supplier_id
        )
        .order_by(Invoice.created_at.desc())
        .limit(limit)
    )
    items = []
    for i in result.all():
        items.append(
            SupplierInvoiceItem(
                id=i.id,
                source_file_name=i.source_file_name,
                invoice_number=i.invoice_number,
                issue_date=i.issue_date,  # type: ignore
                total_ttc=float(i.total_ttc) if i.total_ttc else None,
                currency=i.currency,
                status=i.status.value if hasattr(i.status, "value") else str(i.status),
            )
        )
    return items


class SupplierStats(BaseModel):
    invoice_count: int
    confirmed_count: int
    total_ttc: float
    avg_ttc: float
    last_invoice_date: datetime | None
    first_invoice_date: datetime | None


@router.get("/{supplier_id}/stats", response_model=SupplierStats)
async def get_supplier_stats(
    supplier_id: uuid.UUID, db: DbSession, user: CurrentUser
) -> SupplierStats:
    s = await db.scalar(
        select(Supplier).where(
            Supplier.tenant_id == user.tenant_id, Supplier.id == supplier_id
        )
    )
    if s is None:
        raise HTTPException(status_code=404, detail="supplier_not_found")

    stmt = select(
        func.count(Invoice.id).label("invoice_count"),
        func.sum(
            func.cast(Invoice.status == "confirmed", sa.Integer)  # type: ignore[arg-type]
        ).label("confirmed_count"),
        func.coalesce(func.sum(Invoice.total_ttc), 0).label("total_ttc"),
        func.coalesce(func.avg(Invoice.total_ttc), 0).label("avg_ttc"),
        func.max(Invoice.created_at).label("last_invoice_date"),
        func.min(Invoice.created_at).label("first_invoice_date"),
    ).where(Invoice.supplier_id == supplier_id, Invoice.tenant_id == user.tenant_id)
    row = (await db.execute(stmt)).one()

    return SupplierStats(
        invoice_count=row.invoice_count or 0,
        confirmed_count=int(row.confirmed_count or 0),
        total_ttc=float(row.total_ttc or 0),
        avg_ttc=float(row.avg_ttc or 0),
        last_invoice_date=row.last_invoice_date,
        first_invoice_date=row.first_invoice_date,
    )
