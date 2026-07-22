"""coluna package_md em slices (pacote de fatia persistido)

O markdown do pacote de fatia (docs/fatias/F-XXX.md) é a fonte de verdade
consultável do que a fatia entrega; guardá-lo no banco desacopla do
filesystem (o arquivo em docs/fatias é escrito em best-effort).

Revision ID: e6f2b48a91c5
Revises: d5a9c1e83b62
Create Date: 2026-07-22
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e6f2b48a91c5"
down_revision: Union[str, Sequence[str], None] = "d5a9c1e83b62"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("slices", sa.Column("package_md", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("slices", "package_md")
