import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from raijin_shared.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class CloudDriveProvider(str, enum.Enum):
    GDRIVE = "gdrive"
    DROPBOX = "dropbox"
    ONEDRIVE = "onedrive"


class CloudDriveSource(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "cloud_drive_sources"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "provider",
            "folder_id",
            name="uq_cloud_drive_sources_tenant_folder",
        ),
        Index("ix_cloud_drive_sources_tenant_active", "tenant_id", "is_active"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider: Mapped[CloudDriveProvider] = mapped_column(
        Enum(CloudDriveProvider, name="cloud_drive_provider", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    account_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    folder_id: Mapped[str] = mapped_column(String(255), nullable=False)
    folder_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    access_token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    refresh_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
