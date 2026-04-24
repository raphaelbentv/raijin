"""extend user_role enum (viewer, reviewer)

Revision ID: 20260421_0006
Revises: 20260421_0005
Create Date: 2026-04-21
"""
from typing import Sequence, Union

from alembic import op

revision: str = "20260421_0006"
down_revision: Union[str, None] = "20260421_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ALTER TYPE ... ADD VALUE doit être hors transaction — on isole dans un block autocommit
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'viewer'")
        op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'reviewer'")


def downgrade() -> None:
    # PG ne supporte pas le retrait d'une valeur enum en transaction safe.
    # Pour rollback : créer un nouvel enum, migrer les colonnes, dropper l'ancien.
    pass
