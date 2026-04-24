import hashlib
import re
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile, status
from raijin_shared.models.invoice import InvoiceStatus
from raijin_shared.models.sprint_6_10 import (
    InvoiceCategory,
    InvoiceComment,
    InvoiceShareLink,
)
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.core.audit import log_action
from app.core.permissions import RequireReviewer
from app.core.storage import generate_presigned_url
from app.schemas.invoice import (
    BulkInvoiceRequest,
    BulkInvoiceResponse,
    CorrectionOut,
    InvoiceCategoryIn,
    InvoiceCategoryOut,
    InvoiceCommentIn,
    InvoiceCommentOut,
    InvoiceDetail,
    InvoiceListItem,
    InvoiceListResponse,
    InvoicePatch,
    InvoiceStats,
    PaymentPatch,
    RejectRequest,
    ShareLinkOut,
    UploadResponse,
)
from app.services.invoice import (
    DuplicateInvoiceError,
    FileTooLargeError,
    InvalidTransitionError,
    InvoiceHasErrorsError,
    UnsupportedMimeError,
    confirm_invoice,
    get_invoice,
    invoice_stats,
    list_corrections,
    list_invoices,
    reject_invoice,
    reopen_invoice,
    skip_invoice,
    update_invoice,
    upload_invoice,
)

router = APIRouter(prefix="/invoices", tags=["invoices"])


def _to_detail(invoice) -> InvoiceDetail:
    payload = InvoiceDetail.model_validate(invoice)
    payload.file_url = generate_presigned_url(invoice.source_file_key)
    return payload


@router.post(
    "/upload",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[RequireReviewer],
)
async def upload(
    db: DbSession,
    user: CurrentUser,
    file: UploadFile = File(...),  # noqa: B008
) -> UploadResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="missing_filename")

    content = await file.read()

    try:
        invoice = await upload_invoice(
            db,
            uploader=user,
            filename=file.filename,
            content_type=file.content_type or "application/octet-stream",
            data=content,
        )
    except UnsupportedMimeError as exc:
        raise HTTPException(status_code=415, detail=f"unsupported_mime:{exc}") from exc
    except FileTooLargeError as exc:
        raise HTTPException(status_code=413, detail="file_too_large") from exc
    except DuplicateInvoiceError as exc:
        raise HTTPException(
            status_code=409,
            detail={"error": "duplicate_invoice", "existing_id": str(exc.existing_id)},
        ) from exc

    return UploadResponse(
        id=invoice.id,
        status=invoice.status,
        source_file_name=invoice.source_file_name,
        source_file_size=invoice.source_file_size,
    )


@router.get("", response_model=InvoiceListResponse)
async def list_endpoint(
    db: DbSession,
    user: CurrentUser,
    status_filter: InvoiceStatus | None = None,
    q: str | None = None,
    supplier_id: uuid.UUID | None = None,
    issue_from: str | None = None,
    issue_to: str | None = None,
    amount_min: Decimal | None = None,
    amount_max: Decimal | None = None,
    tag: str | None = None,
    category_id: uuid.UUID | None = None,
    paid: bool | None = None,
    page: int = 1,
    page_size: int = 25,
) -> InvoiceListResponse:
    items, total = await list_invoices(
        db,
        tenant_id=user.tenant_id,
        status=status_filter,
        q=q,
        supplier_id=supplier_id,
        issue_from=datetime.fromisoformat(issue_from).date() if issue_from else None,
        issue_to=datetime.fromisoformat(issue_to).date() if issue_to else None,
        amount_min=amount_min,
        amount_max=amount_max,
        tag=tag,
        category_id=category_id,
        paid=paid,
        page=page,
        page_size=page_size,
    )
    return InvoiceListResponse(
        items=[InvoiceListItem.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/stats", response_model=InvoiceStats)
async def stats(db: DbSession, user: CurrentUser) -> InvoiceStats:
    counters = await invoice_stats(db, tenant_id=user.tenant_id)
    return InvoiceStats(counters=counters)


@router.get("/categories", response_model=list[InvoiceCategoryOut])
async def list_categories(db: DbSession, user: CurrentUser) -> list[InvoiceCategoryOut]:
    items = await db.scalars(
        select(InvoiceCategory)
        .where(InvoiceCategory.tenant_id == user.tenant_id)
        .order_by(InvoiceCategory.name)
    )
    return [InvoiceCategoryOut.model_validate(item) for item in items.all()]


@router.post("/categories", response_model=InvoiceCategoryOut, status_code=201)
async def create_category(
    body: InvoiceCategoryIn, db: DbSession, user: CurrentUser
) -> InvoiceCategoryOut:
    category = InvoiceCategory(
        tenant_id=user.tenant_id,
        name=body.name.strip(),
        color=body.color,
        gl_code=body.gl_code,
    )
    db.add(category)
    await db.commit()
    await db.refresh(category)
    return InvoiceCategoryOut.model_validate(category)


@router.post("/bulk", response_model=BulkInvoiceResponse, dependencies=[RequireReviewer])
async def bulk_action(
    body: BulkInvoiceRequest,
    request: Request,
    db: DbSession,
    user: CurrentUser,
) -> BulkInvoiceResponse:
    processed = 0
    skipped = 0
    for invoice_id in body.ids:
        invoice = await get_invoice(db, tenant_id=user.tenant_id, invoice_id=invoice_id)
        if invoice is None:
            skipped += 1
            continue
        try:
            if body.action == "confirm":
                await confirm_invoice(db, invoice)
            elif body.action == "reject":
                await reject_invoice(db, invoice, body.reason or "Bulk reject")
            elif body.action == "reopen":
                await reopen_invoice(db, invoice)
            elif body.action == "mark_paid":
                invoice.paid_at = datetime.now(UTC).date()
                await db.commit()
            else:
                raise HTTPException(status_code=400, detail="unknown_bulk_action")
            processed += 1
            await log_action(
                db,
                user=user,
                action=f"invoice.bulk.{body.action}",
                entity_type="invoice",
                entity_id=invoice.id,
                request=request,
            )
        except InvalidTransitionError:
            skipped += 1
    return BulkInvoiceResponse(processed=processed, skipped=skipped)


@router.get("/{invoice_id}", response_model=InvoiceDetail)
async def detail(invoice_id: uuid.UUID, db: DbSession, user: CurrentUser) -> InvoiceDetail:
    invoice = await get_invoice(db, tenant_id=user.tenant_id, invoice_id=invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="invoice_not_found")
    return _to_detail(invoice)


@router.patch("/{invoice_id}", response_model=InvoiceDetail, dependencies=[RequireReviewer])
async def patch(
    invoice_id: uuid.UUID,
    body: InvoicePatch,
    db: DbSession,
    user: CurrentUser,
) -> InvoiceDetail:
    invoice = await get_invoice(db, tenant_id=user.tenant_id, invoice_id=invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="invoice_not_found")
    try:
        updated = await update_invoice(db, invoice=invoice, patch=body, user=user)
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _to_detail(updated)


@router.patch("/{invoice_id}/payment", response_model=InvoiceDetail, dependencies=[RequireReviewer])
async def patch_payment(
    invoice_id: uuid.UUID,
    body: PaymentPatch,
    request: Request,
    db: DbSession,
    user: CurrentUser,
) -> InvoiceDetail:
    invoice = await get_invoice(db, tenant_id=user.tenant_id, invoice_id=invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="invoice_not_found")
    invoice.paid_at = body.paid_at
    invoice.payment_method = body.payment_method
    invoice.payment_reference = body.payment_reference
    await db.commit()
    await db.refresh(invoice)
    await db.refresh(invoice, attribute_names=["lines", "supplier"])
    await log_action(
        db,
        user=user,
        action="invoice.payment.update",
        entity_type="invoice",
        entity_id=invoice.id,
        after=body.model_dump(),
        request=request,
    )
    return _to_detail(invoice)


@router.post("/{invoice_id}/approve", response_model=InvoiceDetail, dependencies=[RequireReviewer])
async def approve_invoice(
    invoice_id: uuid.UUID, request: Request, db: DbSession, user: CurrentUser
) -> InvoiceDetail:
    invoice = await get_invoice(db, tenant_id=user.tenant_id, invoice_id=invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="invoice_not_found")
    invoice.approval_status = "approved"
    invoice.approved_by_user_id = user.id
    invoice.approved_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(invoice)
    await db.refresh(invoice, attribute_names=["lines", "supplier"])
    await log_action(
        db,
        user=user,
        action="invoice.approve",
        entity_type="invoice",
        entity_id=invoice.id,
        request=request,
    )
    return _to_detail(invoice)


@router.get("/{invoice_id}/comments", response_model=list[InvoiceCommentOut])
async def list_comments(
    invoice_id: uuid.UUID, db: DbSession, user: CurrentUser
) -> list[InvoiceCommentOut]:
    invoice = await get_invoice(db, tenant_id=user.tenant_id, invoice_id=invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="invoice_not_found")
    comments = await db.scalars(
        select(InvoiceComment)
        .where(
            InvoiceComment.tenant_id == user.tenant_id,
            InvoiceComment.invoice_id == invoice_id,
        )
        .order_by(InvoiceComment.created_at.asc())
    )
    return [InvoiceCommentOut.model_validate(comment) for comment in comments.all()]


@router.post("/{invoice_id}/comments", response_model=InvoiceCommentOut, status_code=201)
async def create_comment(
    invoice_id: uuid.UUID,
    body: InvoiceCommentIn,
    request: Request,
    db: DbSession,
    user: CurrentUser,
) -> InvoiceCommentOut:
    invoice = await get_invoice(db, tenant_id=user.tenant_id, invoice_id=invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="invoice_not_found")
    mentions = sorted(set(re.findall(r"@([\\w.+-]+@[\\w.-]+)", body.body)))
    comment = InvoiceComment(
        tenant_id=user.tenant_id,
        invoice_id=invoice.id,
        user_id=user.id,
        body=body.body,
        mentions=mentions or None,
    )
    db.add(comment)
    await db.commit()
    await db.refresh(comment)
    await log_action(
        db,
        user=user,
        action="invoice.comment.create",
        entity_type="invoice",
        entity_id=invoice.id,
        after={"comment_id": str(comment.id)},
        request=request,
    )
    return InvoiceCommentOut.model_validate(comment)


@router.post("/{invoice_id}/share", response_model=ShareLinkOut, dependencies=[RequireReviewer])
async def create_share_link(
    invoice_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
    expires_days: int = Query(default=30, ge=1, le=365),
) -> ShareLinkOut:
    invoice = await get_invoice(db, tenant_id=user.tenant_id, invoice_id=invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="invoice_not_found")
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(UTC) + timedelta(days=expires_days)
    share = InvoiceShareLink(
        tenant_id=user.tenant_id,
        invoice_id=invoice.id,
        created_by_user_id=user.id,
        token_hash=hashlib.sha256(token.encode("utf-8")).hexdigest(),
        expires_at=expires_at,
    )
    invoice.portal_visible = True
    db.add(share)
    await db.commit()
    return ShareLinkOut(url=f"/portal/invoices/{token}", expires_at=expires_at)


@router.post(
    "/{invoice_id}/confirm", response_model=InvoiceDetail, dependencies=[RequireReviewer]
)
async def confirm(
    invoice_id: uuid.UUID, request: Request, db: DbSession, user: CurrentUser
) -> InvoiceDetail:
    invoice = await get_invoice(db, tenant_id=user.tenant_id, invoice_id=invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="invoice_not_found")
    try:
        confirmed = await confirm_invoice(db, invoice)
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except InvoiceHasErrorsError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "invoice_has_errors",
                "validation_errors": invoice.validation_errors,
            },
        ) from exc
    await log_action(
        db, user=user, action="invoice.confirm", entity_type="invoice",
        entity_id=confirmed.id, request=request,
    )
    return _to_detail(confirmed)


@router.post(
    "/{invoice_id}/reject", response_model=InvoiceDetail, dependencies=[RequireReviewer]
)
async def reject(
    invoice_id: uuid.UUID,
    body: RejectRequest,
    request: Request,
    db: DbSession,
    user: CurrentUser,
) -> InvoiceDetail:
    invoice = await get_invoice(db, tenant_id=user.tenant_id, invoice_id=invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="invoice_not_found")
    try:
        rejected = await reject_invoice(db, invoice, body.reason)
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await log_action(
        db, user=user, action="invoice.reject", entity_type="invoice",
        entity_id=rejected.id, after={"reason": body.reason}, request=request,
    )
    return _to_detail(rejected)


@router.post(
    "/{invoice_id}/skip", response_model=InvoiceDetail, dependencies=[RequireReviewer]
)
async def skip(invoice_id: uuid.UUID, db: DbSession, user: CurrentUser) -> InvoiceDetail:
    invoice = await get_invoice(db, tenant_id=user.tenant_id, invoice_id=invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="invoice_not_found")
    try:
        skipped = await skip_invoice(db, invoice)
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _to_detail(skipped)


@router.post(
    "/{invoice_id}/reopen", response_model=InvoiceDetail, dependencies=[RequireReviewer]
)
async def reopen(
    invoice_id: uuid.UUID, request: Request, db: DbSession, user: CurrentUser
) -> InvoiceDetail:
    invoice = await get_invoice(db, tenant_id=user.tenant_id, invoice_id=invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="invoice_not_found")
    try:
        reopened = await reopen_invoice(db, invoice)
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await log_action(
        db, user=user, action="invoice.reopen", entity_type="invoice",
        entity_id=reopened.id, request=request,
    )
    return _to_detail(reopened)


@router.get("/{invoice_id}/corrections", response_model=list[CorrectionOut])
async def corrections(
    invoice_id: uuid.UUID, db: DbSession, user: CurrentUser
) -> list[CorrectionOut]:
    invoice = await get_invoice(db, tenant_id=user.tenant_id, invoice_id=invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="invoice_not_found")
    items = await list_corrections(db, tenant_id=user.tenant_id, invoice_id=invoice_id)
    return [CorrectionOut.model_validate(i) for i in items]


@router.get("/{invoice_id}/mydata")
async def get_mydata_status(
    invoice_id: uuid.UUID, db: DbSession, user: CurrentUser
):
    from app.schemas.mydata import MyDataSubmissionOut
    from app.services.mydata_config import get_submission

    invoice = await get_invoice(db, tenant_id=user.tenant_id, invoice_id=invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="invoice_not_found")
    submission = await get_submission(
        db, tenant_id=user.tenant_id, invoice_id=invoice_id
    )
    if submission is None:
        return None
    return MyDataSubmissionOut.model_validate(submission)


@router.post("/{invoice_id}/mydata/submit", dependencies=[RequireReviewer])
async def submit_mydata(
    invoice_id: uuid.UUID, db: DbSession, user: CurrentUser
) -> dict:
    invoice = await get_invoice(db, tenant_id=user.tenant_id, invoice_id=invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="invoice_not_found")
    from app.core.celery_client import get_celery

    get_celery().send_task("mydata.submit_invoice", args=[str(invoice.id)])
    return {"invoice_id": str(invoice.id), "status": "queued"}


@router.get("/{invoice_id}/erp")
async def get_erp_status(invoice_id: uuid.UUID, db: DbSession, user: CurrentUser):
    from app.schemas.erp import ErpExportOut
    from app.services.erp_config import get_export

    invoice = await get_invoice(db, tenant_id=user.tenant_id, invoice_id=invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="invoice_not_found")
    export = await get_export(db, tenant_id=user.tenant_id, invoice_id=invoice_id)
    if export is None:
        return None
    return ErpExportOut.model_validate(export)


@router.post("/{invoice_id}/erp/export", dependencies=[RequireReviewer])
async def trigger_erp_export(
    invoice_id: uuid.UUID, db: DbSession, user: CurrentUser
) -> dict:
    invoice = await get_invoice(db, tenant_id=user.tenant_id, invoice_id=invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="invoice_not_found")
    from app.core.celery_client import get_celery

    get_celery().send_task("erp.export_invoice", args=[str(invoice.id)])
    return {"invoice_id": str(invoice.id), "status": "queued"}
