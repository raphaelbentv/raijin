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


class ErpConnectorKind(str, enum.Enum):
    SOFTONE = "softone"
    EPSILON_NET = "epsilon_net"


class ErpExportStatus(str, enum.Enum):
    PENDING = "pending"
    SUBMITTED = "submitted"
    ACKNOWLEDGED = "acknowledged"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ErpConnector(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "erp_connectors"
    __table_args__ = (
        UniqueConstraint("tenant_id", name="uq_erp_connectors_tenant"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    kind: Mapped[ErpConnectorKind] = mapped_column(
        Enum(ErpConnectorKind, name="erp_connector_kind", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    base_url: Mapped[str] = mapped_column(String(512), nullable=False)
    credentials_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    auto_export: Mapped[bool] = mapped_column(default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class ErpExport(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "erp_exports"
    __table_args__ = (
        Index("ix_erp_exports_invoice", "invoice_id"),
        Index("ix_erp_exports_tenant_status", "tenant_id", "status"),
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
        ForeignKey("erp_connectors.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[ErpExportStatus] = mapped_column(
        Enum(ErpExportStatus, name="erp_export_status", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=ErpExportStatus.PENDING,
    )
    external_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    response_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
