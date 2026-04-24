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


class EmailProvider(str, enum.Enum):
    OUTLOOK = "outlook"
    GMAIL = "gmail"


class EmailSource(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "email_sources"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "provider", "account_email", name="uq_email_sources_tenant_account"
        ),
        Index("ix_email_sources_tenant_active", "tenant_id", "is_active"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider: Mapped[EmailProvider] = mapped_column(
        Enum(EmailProvider, name="email_provider", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    account_email: Mapped[str] = mapped_column(String(255), nullable=False)
    access_token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    refresh_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    folder: Mapped[str] = mapped_column(String(128), nullable=False, default="Inbox")
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
