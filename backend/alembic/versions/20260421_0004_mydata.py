"""mydata connectors and submissions

Revision ID: 20260421_0004
Revises: 20260421_0003
Create Date: 2026-04-21

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260421_0004"
down_revision: Union[str, None] = "20260421_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    kind_enum = postgresql.ENUM(
        "epsilon_digital",
        "softone_mydata",
        "aade_direct",
        name="mydata_connector_kind",
        create_type=True,
    )
    kind_enum.create(op.get_bind(), checkfirst=True)

    status_enum = postgresql.ENUM(
        "pending",
        "submitted",
        "acknowledged",
        "failed",
        "cancelled",
        name="mydata_submission_status",
        create_type=True,
    )
    status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "mydata_connectors",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "kind",
            postgresql.ENUM(
                "epsilon_digital",
                "softone_mydata",
                "aade_direct",
                name="mydata_connector_kind",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("base_url", sa.String(length=512), nullable=False),
        sa.Column("credentials_encrypted", sa.Text(), nullable=False),
        sa.Column("issuer_vat_number", sa.String(length=32), nullable=True),
        sa.Column("auto_submit", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", name="uq_mydata_connectors_tenant"),
    )

    op.create_table(
        "mydata_submissions",
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
                name="mydata_submission_status",
                create_type=False,
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("external_id", sa.String(length=128), nullable=True),
        sa.Column("aade_mark", sa.String(length=64), nullable=True),
        sa.Column("uid", sa.String(length=128), nullable=True),
        sa.Column("payload_xml", sa.Text(), nullable=True),
        sa.Column("response_body", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["connector_id"], ["mydata_connectors.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mydata_submissions_invoice", "mydata_submissions", ["invoice_id"])
    op.create_index(
        "ix_mydata_submissions_tenant_status",
        "mydata_submissions",
        ["tenant_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_mydata_submissions_tenant_status", table_name="mydata_submissions")
    op.drop_index("ix_mydata_submissions_invoice", table_name="mydata_submissions")
    op.drop_table("mydata_submissions")
    op.drop_table("mydata_connectors")
    op.execute("DROP TYPE IF EXISTS mydata_submission_status")
    op.execute("DROP TYPE IF EXISTS mydata_connector_kind")
