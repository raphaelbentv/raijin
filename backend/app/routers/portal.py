import hashlib
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException
from raijin_shared.models.invoice import Invoice
from raijin_shared.models.sprint_6_10 import InvoiceShareLink
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import DbSession
from app.core.storage import generate_presigned_url
from app.schemas.invoice import InvoiceDetail

router = APIRouter(prefix="/portal", tags=["portal"])


@router.get("/invoices/{token}", response_model=InvoiceDetail)
async def public_invoice(token: str, db: DbSession) -> InvoiceDetail:
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    share = await db.scalar(
        select(InvoiceShareLink).where(
            InvoiceShareLink.token_hash == token_hash,
            InvoiceShareLink.revoked_at.is_(None),
        )
    )
    now = datetime.now(UTC)
    if share is None or (share.expires_at and share.expires_at < now):
        raise HTTPException(status_code=404, detail="share_link_not_found")

    invoice = await db.scalar(
        select(Invoice)
        .where(
            Invoice.id == share.invoice_id,
            Invoice.tenant_id == share.tenant_id,
            Invoice.portal_visible.is_(True),
        )
        .options(selectinload(Invoice.lines), selectinload(Invoice.supplier))
    )
    if invoice is None:
        raise HTTPException(status_code=404, detail="invoice_not_found")

    payload = InvoiceDetail.model_validate(invoice)
    payload.file_url = generate_presigned_url(invoice.source_file_key)
    return payload
