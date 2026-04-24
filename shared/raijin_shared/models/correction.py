import uuid

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from raijin_shared.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class InvoiceCorrection(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Trace d'une correction appliquée par un utilisateur lors du review.

    Permet d'auditer les modifications humaines et de servir de dataset
    pour du fine-tuning ou de l'amélioration de règles.
    """

    __tablename__ = "invoice_corrections"
    __table_args__ = (
        Index("ix_invoice_corrections_invoice_id", "invoice_id"),
        Index("ix_invoice_corrections_tenant_created", "tenant_id", "created_at"),
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
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    field: Mapped[str] = mapped_column(String(100), nullable=False)
    before_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    after_value: Mapped[str | None] = mapped_column(Text, nullable=True)
