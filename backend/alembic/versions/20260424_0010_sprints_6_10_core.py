"""sprints 6-10 collaboration finance and security core

Revision ID: 20260424_0010
Revises: 20260424_0009
Create Date: 2026-04-24 12:45:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260424_0010"
down_revision: str | None = "20260424_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("locale", sa.String(length=10), nullable=False, server_default="fr"))
    op.add_column("users", sa.Column("notification_preferences", postgresql.JSONB(), nullable=True))
    op.add_column("users", sa.Column("totp_secret_encrypted", sa.String(length=512), nullable=True))
    op.add_column("users", sa.Column("totp_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("users", sa.Column("backup_codes", postgresql.JSONB(), nullable=True))

    op.create_table(
        "invoice_categories",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("color", sa.String(length=32), nullable=True),
        sa.Column("gl_code", sa.String(length=64), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "name", name="uq_invoice_categories_tenant_name"),
    )
    op.create_index(op.f("ix_invoice_categories_tenant_id"), "invoice_categories", ["tenant_id"])

    op.add_column("invoices", sa.Column("paid_at", sa.Date(), nullable=True))
    op.add_column("invoices", sa.Column("payment_method", sa.String(length=64), nullable=True))
    op.add_column("invoices", sa.Column("payment_reference", sa.String(length=255), nullable=True))
    op.add_column("invoices", sa.Column("category_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("invoices", sa.Column("tags", postgresql.JSONB(), nullable=True))
    op.add_column("invoices", sa.Column("custom_fields", postgresql.JSONB(), nullable=True))
    op.add_column(
        "invoices",
        sa.Column("approval_status", sa.String(length=32), nullable=False, server_default="none"),
    )
    op.add_column("invoices", sa.Column("approved_by_user_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("invoices", sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "invoices",
        sa.Column("portal_visible", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_foreign_key(
        "fk_invoices_category_id_invoice_categories",
        "invoices",
        "invoice_categories",
        ["category_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_invoices_approved_by_user_id_users",
        "invoices",
        "users",
        ["approved_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_invoices_tenant_paid", "invoices", ["tenant_id", "paid_at"])
    op.create_index("ix_invoices_tenant_category", "invoices", ["tenant_id", "category_id"])

    op.create_table(
        "invoice_comments",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("mentions", postgresql.JSONB(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_invoice_comments_invoice_created", "invoice_comments", ["invoice_id", "created_at"])
    op.create_index(op.f("ix_invoice_comments_invoice_id"), "invoice_comments", ["invoice_id"])
    op.create_index(op.f("ix_invoice_comments_tenant_id"), "invoice_comments", ["tenant_id"])

    op.create_table(
        "invoice_share_links",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_invoice_share_links_token_hash"),
    )
    op.create_index("ix_invoice_share_links_invoice", "invoice_share_links", ["invoice_id"])
    op.create_index(op.f("ix_invoice_share_links_tenant_id"), "invoice_share_links", ["tenant_id"])

    op.create_table(
        "bank_transactions",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("imported_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("booking_date", sa.Date(), nullable=True),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="EUR"),
        sa.Column("label", sa.String(length=500), nullable=True),
        sa.Column("reference", sa.String(length=255), nullable=True),
        sa.Column("match_score", sa.Numeric(5, 4), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["imported_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_bank_transactions_tenant_date", "bank_transactions", ["tenant_id", "booking_date"])
    op.create_index(op.f("ix_bank_transactions_invoice_id"), "bank_transactions", ["invoice_id"])
    op.create_index(op.f("ix_bank_transactions_tenant_id"), "bank_transactions", ["tenant_id"])

    op.create_table(
        "api_keys",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("key_prefix", sa.String(length=24), nullable=False),
        sa.Column("key_hash", sa.String(length=128), nullable=False),
        sa.Column("scopes", postgresql.JSONB(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key_hash", name="uq_api_keys_key_hash"),
    )
    op.create_index("ix_api_keys_tenant_user", "api_keys", ["tenant_id", "user_id"])
    op.create_index(op.f("ix_api_keys_tenant_id"), "api_keys", ["tenant_id"])
    op.create_index(op.f("ix_api_keys_user_id"), "api_keys", ["user_id"])

    op.create_table(
        "user_sessions",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_hash", sa.String(length=128), nullable=False),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_sessions_tenant_user", "user_sessions", ["tenant_id", "user_id"])
    op.create_index(op.f("ix_user_sessions_session_hash"), "user_sessions", ["session_hash"])
    op.create_index(op.f("ix_user_sessions_tenant_id"), "user_sessions", ["tenant_id"])
    op.create_index(op.f("ix_user_sessions_user_id"), "user_sessions", ["user_id"])

    op.create_table(
        "tenant_ip_rules",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cidr", sa.String(length=64), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "cidr", name="uq_tenant_ip_rules_tenant_cidr"),
    )
    op.create_index(op.f("ix_tenant_ip_rules_tenant_id"), "tenant_ip_rules", ["tenant_id"])

    op.create_table(
        "saml_configs",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_id", sa.String(length=512), nullable=True),
        sa.Column("sso_url", sa.String(length=512), nullable=True),
        sa.Column("certificate", sa.Text(), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", name="uq_saml_configs_tenant"),
    )
    op.create_index(op.f("ix_saml_configs_tenant_id"), "saml_configs", ["tenant_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_saml_configs_tenant_id"), table_name="saml_configs")
    op.drop_table("saml_configs")
    op.drop_index(op.f("ix_tenant_ip_rules_tenant_id"), table_name="tenant_ip_rules")
    op.drop_table("tenant_ip_rules")
    op.drop_index(op.f("ix_user_sessions_user_id"), table_name="user_sessions")
    op.drop_index(op.f("ix_user_sessions_tenant_id"), table_name="user_sessions")
    op.drop_index(op.f("ix_user_sessions_session_hash"), table_name="user_sessions")
    op.drop_index("ix_user_sessions_tenant_user", table_name="user_sessions")
    op.drop_table("user_sessions")
    op.drop_index(op.f("ix_api_keys_user_id"), table_name="api_keys")
    op.drop_index(op.f("ix_api_keys_tenant_id"), table_name="api_keys")
    op.drop_index("ix_api_keys_tenant_user", table_name="api_keys")
    op.drop_table("api_keys")
    op.drop_index(op.f("ix_bank_transactions_tenant_id"), table_name="bank_transactions")
    op.drop_index(op.f("ix_bank_transactions_invoice_id"), table_name="bank_transactions")
    op.drop_index("ix_bank_transactions_tenant_date", table_name="bank_transactions")
    op.drop_table("bank_transactions")
    op.drop_index(op.f("ix_invoice_share_links_tenant_id"), table_name="invoice_share_links")
    op.drop_index("ix_invoice_share_links_invoice", table_name="invoice_share_links")
    op.drop_table("invoice_share_links")
    op.drop_index(op.f("ix_invoice_comments_tenant_id"), table_name="invoice_comments")
    op.drop_index(op.f("ix_invoice_comments_invoice_id"), table_name="invoice_comments")
    op.drop_index("ix_invoice_comments_invoice_created", table_name="invoice_comments")
    op.drop_table("invoice_comments")
    op.drop_index("ix_invoices_tenant_category", table_name="invoices")
    op.drop_index("ix_invoices_tenant_paid", table_name="invoices")
    op.drop_constraint("fk_invoices_approved_by_user_id_users", "invoices", type_="foreignkey")
    op.drop_constraint("fk_invoices_category_id_invoice_categories", "invoices", type_="foreignkey")
    for column in (
        "portal_visible",
        "approved_at",
        "approved_by_user_id",
        "approval_status",
        "custom_fields",
        "tags",
        "category_id",
        "payment_reference",
        "payment_method",
        "paid_at",
    ):
        op.drop_column("invoices", column)
    op.drop_index(op.f("ix_invoice_categories_tenant_id"), table_name="invoice_categories")
    op.drop_table("invoice_categories")
    for column in (
        "backup_codes",
        "totp_enabled",
        "totp_secret_encrypted",
        "notification_preferences",
        "locale",
    ):
        op.drop_column("users", column)
