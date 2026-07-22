"""tabela project_notes (fatia-exemplo F-EX01 / E7)

Anotações livres por projeto — a fatia vertical de exemplo implementada pelo
comando /nova-fatia (estágio E7, PRD Fase 6). UI + API + banco + testes.

Revision ID: a1b2c3d4e5f6
Revises: f7a3c92b6e10
Create Date: 2026-07-22
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "f7a3c92b6e10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "project_notes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_project_notes_project_id", "project_notes", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_project_notes_project_id", table_name="project_notes")
    op.drop_table("project_notes")
