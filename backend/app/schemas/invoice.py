import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict
from raijin_shared.models.invoice import InvoiceStatus


class SupplierOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    vat_number: str | None
    country_code: str | None
    city: str | None


class InvoiceLineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    line_number: int
    description: str | None
    quantity: Decimal | None
    unit_price: Decimal | None
    vat_rate: Decimal | None
    line_total_ht: Decimal | None
    line_total_ttc: Decimal | None


class InvoiceListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: InvoiceStatus
    invoice_number: str | None
    issue_date: date | None
    total_ttc: Decimal | None
    currency: str
    source_file_name: str
    created_at: datetime
    possible_duplicate_of_id: uuid.UUID | None = None
    duplicate_score: Decimal | None = None
    paid_at: date | None = None
    category_id: uuid.UUID | None = None
    tags: list[str] | None = None
    approval_status: str = "none"


class InvoiceDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    supplier_id: uuid.UUID | None
    supplier: SupplierOut | None = None
    uploader_user_id: uuid.UUID
    status: InvoiceStatus
    invoice_number: str | None
    issue_date: date | None
    due_date: date | None
    currency: str
    total_ht: Decimal | None
    total_vat: Decimal | None
    total_ttc: Decimal | None
    source_file_name: str
    source_file_mime: str
    source_file_size: int
    source_file_checksum: str
    ocr_confidence: Decimal | None
    validation_errors: dict | None
    possible_duplicate_of_id: uuid.UUID | None = None
    duplicate_score: Decimal | None = None
    duplicate_reason: str | None = None
    rejected_reason: str | None
    paid_at: date | None = None
    payment_method: str | None = None
    payment_reference: str | None = None
    category_id: uuid.UUID | None = None
    tags: list[str] | None = None
    custom_fields: dict | None = None
    approval_status: str = "none"
    approved_by_user_id: uuid.UUID | None = None
    approved_at: datetime | None = None
    portal_visible: bool = False
    created_at: datetime
    updated_at: datetime
    lines: list[InvoiceLineOut] = []
    file_url: str | None = None


class InvoiceListResponse(BaseModel):
    items: list[InvoiceListItem]
    total: int
    page: int
    page_size: int


class UploadResponse(BaseModel):
    id: uuid.UUID
    status: InvoiceStatus
    source_file_name: str
    source_file_size: int


class InvoiceLinePatch(BaseModel):
    id: uuid.UUID | None = None
    line_number: int
    description: str | None = None
    quantity: Decimal | None = None
    unit_price: Decimal | None = None
    vat_rate: Decimal | None = None
    line_total_ht: Decimal | None = None
    line_total_ttc: Decimal | None = None


class InvoicePatch(BaseModel):
    invoice_number: str | None = None
    issue_date: date | None = None
    due_date: date | None = None
    currency: str | None = None
    total_ht: Decimal | None = None
    total_vat: Decimal | None = None
    total_ttc: Decimal | None = None
    supplier_id: uuid.UUID | None = None
    paid_at: date | None = None
    payment_method: str | None = None
    payment_reference: str | None = None
    category_id: uuid.UUID | None = None
    tags: list[str] | None = None
    custom_fields: dict | None = None
    lines: list[InvoiceLinePatch] | None = None


class RejectRequest(BaseModel):
    reason: str


class InvoiceStats(BaseModel):
    counters: dict[str, int]


class BulkInvoiceRequest(BaseModel):
    ids: list[uuid.UUID]
    action: str
    reason: str | None = None


class BulkInvoiceResponse(BaseModel):
    processed: int
    skipped: int


class PaymentPatch(BaseModel):
    paid_at: date | None = None
    payment_method: str | None = None
    payment_reference: str | None = None


class InvoiceCategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    color: str | None = None
    gl_code: str | None = None


class InvoiceCategoryIn(BaseModel):
    name: str
    color: str | None = None
    gl_code: str | None = None


class InvoiceCommentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    invoice_id: uuid.UUID
    user_id: uuid.UUID | None
    body: str
    mentions: list[str] | None
    created_at: datetime


class InvoiceCommentIn(BaseModel):
    body: str


class ShareLinkOut(BaseModel):
    url: str
    expires_at: datetime | None = None


class CorrectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID | None
    field: str
    before_value: str | None
    after_value: str | None
    created_at: datetime
