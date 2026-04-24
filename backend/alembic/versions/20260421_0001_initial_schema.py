"""initial schema

Revision ID: 20260421_0001
Revises:
Create Date: 2026-04-21

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260421_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("country_code", sa.String(length=2), nullable=False, server_default="GR"),
        sa.Column("default_currency", sa.String(length=3), nullable=False, server_default="EUR"),
        sa.Column("default_locale", sa.String(length=10), nullable=False, server_default="fr"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_tenants_slug", "tenants", ["slug"])

    user_role = postgresql.ENUM("admin", "user", name="user_role", create_type=True)
    user_role.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("role", postgresql.ENUM("admin", "user", name="user_role", create_type=False), nullable=False, server_default="user"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),
    )
    op.create_index("ix_users_tenant_id", "users", ["tenant_id"])
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "suppliers",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("vat_number", sa.String(length=32), nullable=True),
        sa.Column("country_code", sa.String(length=2), nullable=True),
        sa.Column("address_line1", sa.String(length=255), nullable=True),
        sa.Column("address_line2", sa.String(length=255), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=True),
        sa.Column("postal_code", sa.String(length=20), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "vat_number", name="uq_suppliers_tenant_vat"),
    )
    op.create_index("ix_suppliers_tenant_id", "suppliers", ["tenant_id"])
    op.create_index("ix_suppliers_vat_number", "suppliers", ["vat_number"])

    invoice_status = postgresql.ENUM(
        "uploaded",
        "processing",
        "ready_for_review",
        "confirmed",
        "rejected",
        "failed",
        name="invoice_status",
        create_type=True,
    )
    invoice_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "invoices",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("uploader_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("supplier_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(
                "uploaded",
                "processing",
                "ready_for_review",
                "confirmed",
                "rejected",
                "failed",
                name="invoice_status",
                create_type=False,
            ),
            nullable=False,
            server_default="uploaded",
        ),
        sa.Column("invoice_number", sa.String(length=100), nullable=True),
        sa.Column("issue_date", sa.Date(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="EUR"),
        sa.Column("total_ht", sa.Numeric(14, 2), nullable=True),
        sa.Column("total_vat", sa.Numeric(14, 2), nullable=True),
        sa.Column("total_ttc", sa.Numeric(14, 2), nullable=True),
        sa.Column("source_file_key", sa.String(length=512), nullable=False),
        sa.Column("source_file_mime", sa.String(length=100), nullable=False),
        sa.Column("source_file_size", sa.Integer(), nullable=False),
        sa.Column("source_file_checksum", sa.String(length=64), nullable=False),
        sa.Column("source_file_name", sa.String(length=255), nullable=False),
        sa.Column("ocr_job_id", sa.String(length=100), nullable=True),
        sa.Column("ocr_raw", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("ocr_confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("validation_errors", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("confirmed_at", sa.Date(), nullable=True),
        sa.Column("rejected_reason", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploader_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "supplier_id",
            "invoice_number",
            name="uq_invoices_tenant_supplier_number",
        ),
    )
    op.create_index("ix_invoices_tenant_id", "invoices", ["tenant_id"])
    op.create_index("ix_invoices_source_file_checksum", "invoices", ["source_file_checksum"])
    op.create_index("ix_invoices_tenant_status", "invoices", ["tenant_id", "status"])
    op.create_index("ix_invoices_tenant_created", "invoices", ["tenant_id", "created_at"])

    op.create_table(
        "invoice_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("quantity", sa.Numeric(14, 4), nullable=True),
        sa.Column("unit_price", sa.Numeric(14, 4), nullable=True),
        sa.Column("vat_rate", sa.Numeric(5, 4), nullable=True),
        sa.Column("line_total_ht", sa.Numeric(14, 2), nullable=True),
        sa.Column("line_total_ttc", sa.Numeric(14, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_invoice_lines_invoice_id", "invoice_lines", ["invoice_id"])

    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("before_state", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("after_state", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("ip_address", postgresql.INET(), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_logs_tenant_id", "audit_logs", ["tenant_id"])
    op.create_index("ix_audit_logs_tenant_created", "audit_logs", ["tenant_id", "created_at"])
    op.create_index("ix_audit_logs_entity", "audit_logs", ["entity_type", "entity_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_logs_entity", table_name="audit_logs")
    op.drop_index("ix_audit_logs_tenant_created", table_name="audit_logs")
    op.drop_index("ix_audit_logs_tenant_id", table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_index("ix_invoice_lines_invoice_id", table_name="invoice_lines")
    op.drop_table("invoice_lines")

    op.drop_index("ix_invoices_tenant_created", table_name="invoices")
    op.drop_index("ix_invoices_tenant_status", table_name="invoices")
    op.drop_index("ix_invoices_source_file_checksum", table_name="invoices")
    op.drop_index("ix_invoices_tenant_id", table_name="invoices")
    op.drop_table("invoices")
    op.execute("DROP TYPE IF EXISTS invoice_status")

    op.drop_index("ix_suppliers_vat_number", table_name="suppliers")
    op.drop_index("ix_suppliers_tenant_id", table_name="suppliers")
    op.drop_table("suppliers")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_tenant_id", table_name="users")
    op.drop_table("users")
    op.execute("DROP TYPE IF EXISTS user_role")

    op.drop_index("ix_tenants_slug", table_name="tenants")
    op.drop_table("tenants")
