from __future__ import annotations

import csv
from datetime import date, datetime
from decimal import Decimal
from io import StringIO

from fastapi import APIRouter, File, Query, UploadFile
from raijin_shared.models.invoice import Invoice, InvoiceStatus
from raijin_shared.models.sprint_6_10 import BankTransaction
from sqlalchemy import extract, func, select

from app.api.deps import CurrentUser, DbSession
from app.core.permissions import RequireReviewer

router = APIRouter(prefix="/reports", tags=["reports"], dependencies=[RequireReviewer])


@router.get("/vat")
async def vat_report(
    db: DbSession,
    user: CurrentUser,
    year: int,
    quarter: int = Query(default=1, ge=1, le=4),
) -> dict[str, object]:
    start_month = ((quarter - 1) * 3) + 1
    months = [start_month, start_month + 1, start_month + 2]
    result = await db.execute(
        select(
            func.coalesce(func.sum(Invoice.total_ht), 0),
            func.coalesce(func.sum(Invoice.total_vat), 0),
            func.coalesce(func.sum(Invoice.total_ttc), 0),
            func.count(Invoice.id),
        ).where(
            Invoice.tenant_id == user.tenant_id,
            Invoice.status == InvoiceStatus.CONFIRMED,
            extract("year", Invoice.issue_date) == year,
            extract("month", Invoice.issue_date).in_(months),
        )
    )
    total_ht, total_vat, total_ttc, count = result.one()
    return {
        "year": year,
        "quarter": quarter,
        "invoice_count": int(count),
        "total_ht": str(total_ht),
        "total_vat": str(total_vat),
        "total_ttc": str(total_ttc),
    }


@router.get("/profit-loss")
async def profit_loss_report(db: DbSession, user: CurrentUser, year: int) -> dict[str, object]:
    rows = await db.execute(
        select(
            extract("month", Invoice.issue_date).label("month"),
            func.coalesce(func.sum(Invoice.total_ht), 0),
            func.count(Invoice.id),
        )
        .where(
            Invoice.tenant_id == user.tenant_id,
            Invoice.status == InvoiceStatus.CONFIRMED,
            extract("year", Invoice.issue_date) == year,
        )
        .group_by("month")
        .order_by("month")
    )
    return {
        "year": year,
        "months": [
            {"month": int(month), "expense_ht": str(amount), "invoice_count": int(count)}
            for month, amount, count in rows.all()
        ],
    }


@router.get("/aging")
async def aging_report(db: DbSession, user: CurrentUser) -> dict[str, object]:
    today = date.today()
    invoices = await db.scalars(
        select(Invoice).where(
            Invoice.tenant_id == user.tenant_id,
            Invoice.status == InvoiceStatus.CONFIRMED,
            Invoice.paid_at.is_(None),
        )
    )
    buckets = {
        "0-30": Decimal("0"),
        "30-60": Decimal("0"),
        "60-90": Decimal("0"),
        ">90": Decimal("0"),
    }
    for invoice in invoices.all():
        due = invoice.due_date or invoice.issue_date or today
        age = max(0, (today - due).days)
        key = "0-30" if age <= 30 else "30-60" if age <= 60 else "60-90" if age <= 90 else ">90"
        buckets[key] += invoice.total_ttc or Decimal("0")
    return {"as_of": today.isoformat(), "buckets": {key: str(value) for key, value in buckets.items()}}


@router.post("/reconciliation/import")
async def import_bank_csv(
    db: DbSession,
    user: CurrentUser,
    file: UploadFile = File(...),  # noqa: B008
) -> dict[str, int]:
    content = (await file.read()).decode("utf-8-sig")
    reader = csv.DictReader(StringIO(content))
    imported = 0
    matched = 0
    for row in reader:
        amount = Decimal((row.get("amount") or row.get("montant") or "0").replace(",", "."))
        booking = row.get("date") or row.get("booking_date")
        booking_date = datetime.fromisoformat(booking).date() if booking else None
        candidate = await db.scalar(
            select(Invoice)
            .where(
                Invoice.tenant_id == user.tenant_id,
                Invoice.paid_at.is_(None),
                Invoice.total_ttc >= amount - Decimal("0.50"),
                Invoice.total_ttc <= amount + Decimal("0.50"),
            )
            .order_by(Invoice.issue_date.desc().nullslast())
            .limit(1)
        )
        tx = BankTransaction(
            tenant_id=user.tenant_id,
            imported_by_user_id=user.id,
            invoice_id=candidate.id if candidate else None,
            booking_date=booking_date,
            amount=amount,
            currency=row.get("currency") or "EUR",
            label=row.get("label") or row.get("libelle"),
            reference=row.get("reference"),
            match_score=Decimal("0.9000") if candidate else None,
        )
        db.add(tx)
        if candidate:
            candidate.paid_at = booking_date or date.today()
            candidate.payment_method = "bank_transfer"
            candidate.payment_reference = row.get("reference")
            matched += 1
        imported += 1
    await db.commit()
    return {"imported": imported, "matched": matched}
