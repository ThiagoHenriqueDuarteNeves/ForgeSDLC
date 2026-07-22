"""tabela llm_calls (métricas por estágio: tokens, custo, latência)

Observabilidade da Fase 7 (PRD §6): uma linha por chamada de LLM, gravada pelo
único ponto de saída tipada (llm.structured_call). A agregação por estágio/run
responde na UI "quanto custou este run e onde foi o tempo".

Revision ID: f7a3c92b6e10
Revises: e6f2b48a91c5
Create Date: 2026-07-22
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f7a3c92b6e10"
down_revision: Union[str, Sequence[str], None] = "e6f2b48a91c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "llm_calls",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("runs.id"), nullable=True),
        sa.Column("node", sa.String(length=32), nullable=False),
        sa.Column("stage", sa.String(length=8), nullable=False),
        sa.Column("model", sa.String(length=64), nullable=False),
        sa.Column("tokens_in", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tokens_out", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Float(), nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_llm_calls_run_id", "llm_calls", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_llm_calls_run_id", table_name="llm_calls")
    op.drop_table("llm_calls")
