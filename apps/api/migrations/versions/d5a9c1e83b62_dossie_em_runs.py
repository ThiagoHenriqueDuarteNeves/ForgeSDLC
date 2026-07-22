"""coluna dossie em runs (dossiê como artefato de primeira classe)

O dossiê do Grill Me deixa de viver só no estado do checkpointer e passa a
ser persistido em domínio (consultável, exportável, auditável), como o PRD §4
pede ("Dossiê do Sistema persistido").

Revision ID: d5a9c1e83b62
Revises: c3f8b2a15d47
Create Date: 2026-07-22
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d5a9c1e83b62"
down_revision: Union[str, Sequence[str], None] = "c3f8b2a15d47"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("runs", sa.Column("dossie", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("runs", "dossie")
