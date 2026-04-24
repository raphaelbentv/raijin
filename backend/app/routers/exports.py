from datetime import date
from typing import Annotated
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from raijin_shared.models.invoice import InvoiceStatus

from app.api.deps import CurrentUser, DbSession
from app.services.export import (
    build_excel,
    build_filename,
    query_invoices_for_export,
)

router = APIRouter(prefix="/exports", tags=["exports"])


@router.get("/excel")
async def export_excel(
    db: DbSession,
    user: CurrentUser,
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
    ids: Annotated[list[UUID] | None, Query()] = None,
    supplier_id: UUID | None = None,
    status_filter: InvoiceStatus | None = None,
) -> StreamingResponse:
    invoices = await query_invoices_for_export(
        db,
        tenant_id=user.tenant_id,
        ids=ids,
        date_from=date_from,
        date_to=date_to,
        supplier_id=supplier_id,
        status=status_filter,
    )

    xlsx_bytes = build_excel(invoices, tenant_name=user.tenant.name)
    filename = build_filename(user.tenant.slug, date_from=date_from, date_to=date_to)

    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"; filename*=UTF-8\'\'{quote(filename)}',
        "Content-Length": str(len(xlsx_bytes)),
    }
    return StreamingResponse(
        iter([xlsx_bytes]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )
