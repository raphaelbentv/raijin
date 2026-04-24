import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from raijin_shared.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class MyDataConnectorKind(str, enum.Enum):
    EPSILON_DIGITAL = "epsilon_digital"
    SOFTONE_MYDATA = "softone_mydata"
    AADE_DIRECT = "aade_direct"


class MyDataSubmissionStatus(str, enum.Enum):
    PENDING = "pending"
    SUBMITTED = "submitted"
    ACKNOWLEDGED = "acknowledged"
    FAILED = "failed"
    CANCELLED = "cancelled"


class MyDataConnector(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "mydata_connectors"
    __table_args__ = (
        UniqueConstraint("tenant_id", name="uq_mydata_connectors_tenant"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    kind: Mapped[MyDataConnectorKind] = mapped_column(
        Enum(MyDataConnectorKind, name="mydata_connector_kind", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    base_url: Mapped[str] = mapped_column(String(512), nullable=False)
    credentials_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    issuer_vat_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    auto_submit: Mapped[bool] = mapped_column(default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class MyDataSubmission(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "mydata_submissions"
    __table_args__ = (
        Index("ix_mydata_submissions_invoice", "invoice_id"),
        Index("ix_mydata_submissions_tenant_status", "tenant_id", "status"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("invoices.id", ondelete="CASCADE"),
        nullable=False,
    )
    connector_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("mydata_connectors.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[MyDataSubmissionStatus] = mapped_column(
        Enum(MyDataSubmissionStatus, name="mydata_submission_status", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=MyDataSubmissionStatus.PENDING,
    )
    external_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    aade_mark: Mapped[str | None] = mapped_column(String(64), nullable=True)
    uid: Mapped[str | None] = mapped_column(String(128), nullable=True)

    payload_xml: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
