"""invoice duplicate candidates

Revision ID: 20260424_0009
Revises: 20260422_0008
Create Date: 2026-04-24
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260424_0009"
down_revision: str | None = "20260422_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("uq_invoices_tenant_supplier_number", "invoices", type_="unique")
    op.add_column(
        "invoices",
        sa.Column("possible_duplicate_of_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "invoices",
        sa.Column("duplicate_score", sa.Numeric(5, 4), nullable=True),
    )
    op.add_column(
        "invoices",
        sa.Column("duplicate_reason", sa.String(length=255), nullable=True),
    )
    op.create_foreign_key(
        "fk_invoices_possible_duplicate",
        "invoices",
        "invoices",
        ["possible_duplicate_of_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_invoices_possible_duplicate",
        "invoices",
        ["tenant_id", "possible_duplicate_of_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_invoices_possible_duplicate", table_name="invoices")
    op.drop_constraint("fk_invoices_possible_duplicate", "invoices", type_="foreignkey")
    op.drop_column("invoices", "duplicate_reason")
    op.drop_column("invoices", "duplicate_score")
    op.drop_column("invoices", "possible_duplicate_of_id")
    op.create_unique_constraint(
        "uq_invoices_tenant_supplier_number",
        "invoices",
        ["tenant_id", "supplier_id", "invoice_number"],
    )
