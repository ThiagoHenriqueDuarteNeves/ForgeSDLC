"""trigger de imutabilidade de RN aprovada (PRD §4/E3.1)

Uma RN aprovada nunca tem o texto alterado. Isso não pode depender só do
código da aplicação — um trigger no banco garante a invariante mesmo contra
UPDATE direto. Transições de `status` (aprovada→contestada→superseded)
continuam permitidas; o que é bloqueado é a mudança de `text` numa linha que
já está aprovada.

Revision ID: b7e4a1c9d2f3
Revises: 1443ad845c22
Create Date: 2026-07-22
"""
from typing import Sequence, Union

from alembic import op

revision: str = "b7e4a1c9d2f3"
down_revision: Union[str, Sequence[str], None] = "1443ad845c22"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION forbid_approved_rule_text_change()
        RETURNS trigger AS $$
        BEGIN
            IF OLD.status = 'aprovada' AND NEW.text IS DISTINCT FROM OLD.text THEN
                RAISE EXCEPTION
                    'RN aprovada e imutavel: o texto de % nao pode ser alterado',
                    OLD.code
                USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_business_rules_immutable
        BEFORE UPDATE ON business_rules
        FOR EACH ROW
        EXECUTE FUNCTION forbid_approved_rule_text_change();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_business_rules_immutable ON business_rules")
    op.execute("DROP FUNCTION IF EXISTS forbid_approved_rule_text_change()")
