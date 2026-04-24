"""invoice corrections

Revision ID: 20260421_0002
Revises: 20260421_0001
Create Date: 2026-04-21

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260421_0002"
down_revision: str | None = "20260421_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "invoice_corrections",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("field", sa.String(length=100), nullable=False),
        sa.Column("before_value", sa.Text(), nullable=True),
        sa.Column("after_value", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_invoice_corrections_invoice_id", "invoice_corrections", ["invoice_id"])
    op.create_index(
        "ix_invoice_corrections_tenant_created",
        "invoice_corrections",
        ["tenant_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_invoice_corrections_tenant_created", table_name="invoice_corrections")
    op.drop_index("ix_invoice_corrections_invoice_id", table_name="invoice_corrections")
    op.drop_table("invoice_corrections")
