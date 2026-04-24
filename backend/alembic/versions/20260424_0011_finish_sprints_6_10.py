"""finish sprints 6-10 indexes and gdpr deletion requests

Revision ID: 20260424_0011
Revises: 20260424_0010
Create Date: 2026-04-24 16:10:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260424_0011"
down_revision: str | None = "20260424_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.create_index(
        "ix_invoices_invoice_number_trgm",
        "invoices",
        ["invoice_number"],
        postgresql_using="gin",
        postgresql_ops={"invoice_number": "gin_trgm_ops"},
    )
    op.create_index(
        "ix_invoices_source_file_name_trgm",
        "invoices",
        ["source_file_name"],
        postgresql_using="gin",
        postgresql_ops={"source_file_name": "gin_trgm_ops"},
    )
    op.create_index(
        "ix_suppliers_name_trgm",
        "suppliers",
        ["name"],
        postgresql_using="gin",
        postgresql_ops={"name": "gin_trgm_ops"},
    )
    op.create_table(
        "gdpr_deletion_requests",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_gdpr_deletion_requests_tenant_user",
        "gdpr_deletion_requests",
        ["tenant_id", "user_id"],
    )
    op.create_index(
        "ix_gdpr_deletion_requests_status_scheduled",
        "gdpr_deletion_requests",
        ["status", "scheduled_for"],
    )
    op.create_index(
        op.f("ix_gdpr_deletion_requests_tenant_id"),
        "gdpr_deletion_requests",
        ["tenant_id"],
    )
    op.create_index(
        op.f("ix_gdpr_deletion_requests_user_id"),
        "gdpr_deletion_requests",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_gdpr_deletion_requests_user_id"), table_name="gdpr_deletion_requests")
    op.drop_index(op.f("ix_gdpr_deletion_requests_tenant_id"), table_name="gdpr_deletion_requests")
    op.drop_index("ix_gdpr_deletion_requests_status_scheduled", table_name="gdpr_deletion_requests")
    op.drop_index("ix_gdpr_deletion_requests_tenant_user", table_name="gdpr_deletion_requests")
    op.drop_table("gdpr_deletion_requests")
    op.drop_index("ix_suppliers_name_trgm", table_name="suppliers", postgresql_using="gin")
    op.drop_index("ix_invoices_source_file_name_trgm", table_name="invoices", postgresql_using="gin")
    op.drop_index("ix_invoices_invoice_number_trgm", table_name="invoices", postgresql_using="gin")
