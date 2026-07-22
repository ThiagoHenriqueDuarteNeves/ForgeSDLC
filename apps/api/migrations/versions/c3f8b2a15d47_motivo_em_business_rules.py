"""coluna motivo em business_rules (contestação e supersede, PRD §4/E3.1)

Guarda o motivo de uma RN contestada e a justificativa de uma RN que supera
outra (`supersedes`). Faz parte do modelo append-only: nada é apagado, tudo
é rastreável.

Revision ID: c3f8b2a15d47
Revises: b7e4a1c9d2f3
Create Date: 2026-07-22
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c3f8b2a15d47"
down_revision: Union[str, Sequence[str], None] = "b7e4a1c9d2f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "business_rules", sa.Column("motivo", sa.Text(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("business_rules", "motivo")
