"""Critério de aceite (PRD §4/E3.1): RN aprovada é imutável no BANCO.

Prova que o trigger `trg_business_rules_immutable` impede UPDATE no texto de
uma RN aprovada — mesmo por SQL direto, não só pela camada de aplicação.
Requer o Postgres de pé com a migração aplicada (alembic upgrade head).
Insere em transação e faz rollback ao fim.
"""

import pytest
from sqlalchemy.exc import DBAPIError

from src.db import SessionLocal
from src.models import BusinessRule, Project, RuleStatus, Run


@pytest.fixture
def session():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


def _rn(session, status: RuleStatus) -> BusinessRule:
    project = Project(name="proj-imut")
    session.add(project)
    session.flush()
    run = Run(project_id=project.id, stage="E3")
    session.add(run)
    session.flush()
    rn = BusinessRule(
        run_id=run.id, code="RN-001", text="texto original", fonte="Q-01", status=status
    )
    session.add(rn)
    session.flush()
    return rn


def test_update_texto_de_rn_aprovada_e_bloqueado(session):
    rn = _rn(session, RuleStatus.aprovada)
    rn.text = "texto adulterado"
    with pytest.raises(DBAPIError):
        session.flush()  # o trigger dispara e aborta


def test_update_texto_de_rn_proposta_e_permitido(session):
    rn = _rn(session, RuleStatus.proposta)
    rn.text = "ainda em proposta, pode mudar"
    session.flush()  # não levanta
    assert rn.text == "ainda em proposta, pode mudar"


def test_transicao_de_status_de_rn_aprovada_e_permitida(session):
    # imutabilidade é do TEXTO; contestar (aprovada→contestada) é permitido.
    rn = _rn(session, RuleStatus.aprovada)
    rn.status = RuleStatus.contestada
    session.flush()  # não levanta
    assert rn.status == RuleStatus.contestada
