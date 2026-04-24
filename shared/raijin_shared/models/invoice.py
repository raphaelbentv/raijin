import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from raijin_shared.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class InvoiceStatus(str, enum.Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    READY_FOR_REVIEW = "ready_for_review"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    FAILED = "failed"


class Invoice(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "invoices"
    __table_args__ = (
        Index("ix_invoices_tenant_status", "tenant_id", "status"),
        Index("ix_invoices_tenant_created", "tenant_id", "created_at"),
        Index("ix_invoices_possible_duplicate", "tenant_id", "possible_duplicate_of_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    uploader_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("suppliers.id", ondelete="SET NULL"),
        nullable=True,
    )

    status: Mapped[InvoiceStatus] = mapped_column(
        Enum(InvoiceStatus, name="invoice_status", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=InvoiceStatus.UPLOADED,
    )

    invoice_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    issue_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")

    total_ht: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    total_vat: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    total_ttc: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)

    source_file_key: Mapped[str] = mapped_column(String(512), nullable=False)
    source_file_mime: Mapped[str] = mapped_column(String(100), nullable=False)
    source_file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    source_file_checksum: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_file_name: Mapped[str] = mapped_column(String(255), nullable=False)

    ocr_job_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ocr_raw: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ocr_confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    validation_errors: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    possible_duplicate_of_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("invoices.id", ondelete="SET NULL"),
        nullable=True,
    )
    duplicate_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    duplicate_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    confirmed_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    rejected_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    paid_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    payment_method: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payment_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("invoice_categories.id", ondelete="SET NULL"),
        nullable=True,
    )
    tags: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    custom_fields: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    approval_status: Mapped[str] = mapped_column(String(32), nullable=False, default="none")
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    portal_visible: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    lines: Mapped[list["InvoiceLine"]] = relationship(
        "InvoiceLine",
        back_populates="invoice",
        cascade="all, delete-orphan",
    )
    supplier: Mapped["Supplier | None"] = relationship(  # noqa: F821
        "Supplier",
        lazy="joined",
    )


class InvoiceLine(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "invoice_lines"

    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("invoices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    vat_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    line_total_ht: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    line_total_ttc: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)

    invoice: Mapped[Invoice] = relationship("Invoice", back_populates="lines")
