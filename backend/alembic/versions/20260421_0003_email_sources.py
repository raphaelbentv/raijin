"""email sources

Revision ID: 20260421_0003
Revises: 20260421_0002
Create Date: 2026-04-21

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260421_0003"
down_revision: Union[str, None] = "20260421_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    email_provider = postgresql.ENUM("outlook", "gmail", name="email_provider", create_type=True)
    email_provider.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "email_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "provider",
            postgresql.ENUM("outlook", "gmail", name="email_provider", create_type=False),
            nullable=False,
        ),
        sa.Column("account_email", sa.String(length=255), nullable=False),
        sa.Column("access_token_encrypted", sa.Text(), nullable=False),
        sa.Column("refresh_token_encrypted", sa.Text(), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("folder", sa.String(length=128), nullable=False, server_default="Inbox"),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "provider", "account_email", name="uq_email_sources_tenant_account"
        ),
    )
    op.create_index("ix_email_sources_tenant_active", "email_sources", ["tenant_id", "is_active"])


def downgrade() -> None:
    op.drop_index("ix_email_sources_tenant_active", table_name="email_sources")
    op.drop_table("email_sources")
    op.execute("DROP TYPE IF EXISTS email_provider")
