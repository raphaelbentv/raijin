from typing import Annotated

from fastapi import APIRouter, Depends, Response
from raijin_shared.models.correction import InvoiceCorrection
from raijin_shared.models.invoice import Invoice, InvoiceStatus
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, DbSession
from app.core.database import get_db
from app.core.observability import render_prometheus_metrics

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/prometheus", include_in_schema=False)
async def prometheus_metrics(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    return Response(
        content=await render_prometheus_metrics(db),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


@router.get("")
async def metrics(db: DbSession, user: CurrentUser) -> dict[str, object]:
    """Snapshot métriques pour le tenant courant (MVP, pas Prometheus)."""
    counters = {s.value: 0 for s in InvoiceStatus}
    result = await db.execute(
        select(Invoice.status, func.count(Invoice.id))
        .where(Invoice.tenant_id == user.tenant_id)
        .group_by(Invoice.status)
    )
    total = 0
    for status_value, count in result.all():
        key = status_value.value if hasattr(status_value, "value") else str(status_value)
        counters[key] = count
        total += count

    ocr_success_rate = None
    processed = counters[InvoiceStatus.READY_FOR_REVIEW.value] + counters[InvoiceStatus.CONFIRMED.value]
    failed = counters[InvoiceStatus.FAILED.value]
    if processed + failed > 0:
        ocr_success_rate = round(processed / (processed + failed), 3)

    confidence_avg = await db.scalar(
        select(func.avg(Invoice.ocr_confidence)).where(
            Invoice.tenant_id == user.tenant_id,
            Invoice.ocr_confidence.is_not(None),
        )
    )

    correction_count = await db.scalar(
        select(func.count(InvoiceCorrection.id)).where(
            InvoiceCorrection.tenant_id == user.tenant_id,
        )
    )

    return {
        "tenant_id": str(user.tenant_id),
        "invoices": {
            "counters": counters,
            "total": total,
        },
        "ocr": {
            "success_rate": ocr_success_rate,
            "mean_confidence": float(confidence_avg) if confidence_avg is not None else None,
        },
        "review": {
            "corrections_total": int(correction_count or 0),
        },
    }
