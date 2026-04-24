"""erp connectors and exports

Revision ID: 20260421_0005
Revises: 20260421_0004
Create Date: 2026-04-21

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260421_0005"
down_revision: str | None = "20260421_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    kind_enum = postgresql.ENUM(
        "softone", "epsilon_net", name="erp_connector_kind", create_type=True
    )
    kind_enum.create(op.get_bind(), checkfirst=True)

    status_enum = postgresql.ENUM(
        "pending",
        "submitted",
        "acknowledged",
        "failed",
        "cancelled",
        name="erp_export_status",
        create_type=True,
    )
    status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "erp_connectors",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "kind",
            postgresql.ENUM(
                "softone", "epsilon_net", name="erp_connector_kind", create_type=False
            ),
            nullable=False,
        ),
        sa.Column("base_url", sa.String(length=512), nullable=False),
        sa.Column("credentials_encrypted", sa.Text(), nullable=False),
        sa.Column("auto_export", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", name="uq_erp_connectors_tenant"),
    )

    op.create_table(
        "erp_exports",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("connector_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(
                "pending",
                "submitted",
                "acknowledged",
                "failed",
                "cancelled",
                name="erp_export_status",
                create_type=False,
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("external_id", sa.String(length=128), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("response_body", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["connector_id"], ["erp_connectors.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_erp_exports_invoice", "erp_exports", ["invoice_id"])
    op.create_index(
        "ix_erp_exports_tenant_status", "erp_exports", ["tenant_id", "status"]
    )


def downgrade() -> None:
    op.drop_index("ix_erp_exports_tenant_status", table_name="erp_exports")
    op.drop_index("ix_erp_exports_invoice", table_name="erp_exports")
    op.drop_table("erp_exports")
    op.drop_table("erp_connectors")
    op.execute("DROP TYPE IF EXISTS erp_export_status")
    op.execute("DROP TYPE IF EXISTS erp_connector_kind")
