"""Correção append-only de RN (PRD §4/E3.1): contestada → supersede.

Prova que resolver uma contestação cria uma RN NOVA que supera a original
(sem editar a antiga), marca a original como `superseded` e as histórias
derivadas como `stale` — tudo auditado.

Usa transação externa com savepoint: os `commit()` internos do serviço viram
releases de savepoint e o rollback final desfaz tudo (isola o banco).
"""

import pytest
from sqlalchemy.orm import Session

from src.db import engine
from src.models import (
    AuditLog,
    BusinessRule,
    Epic,
    Project,
    RuleStatus,
    Run,
    Story,
    StoryRule,
)
from src.services_regras import criar_correcao


@pytest.fixture
def session():
    conn = engine.connect()
    trans = conn.begin()
    s = Session(bind=conn, join_transaction_mode="create_savepoint")
    try:
        yield s
    finally:
        s.close()
        trans.rollback()
        conn.close()


def _cenario(session, status=RuleStatus.contestada) -> tuple[int, BusinessRule, Story]:
    project = Project(name="proj-supersede")
    session.add(project)
    session.flush()
    run = Run(project_id=project.id, stage="E3")
    session.add(run)
    session.flush()
    rn = BusinessRule(
        run_id=run.id,
        code="RN-001",
        text="regra errada",
        fonte="Q-01",
        status=status,
        motivo="valor de prazo trocado",
    )
    session.add(rn)
    session.flush()
    epic = Epic(run_id=run.id, title="Épico")
    session.add(epic)
    session.flush()
    story = Story(epic_id=epic.id, title="US derivada", status="aprovada")
    session.add(story)
    session.flush()
    session.add(StoryRule(story_id=story.id, business_rule_id=rn.id))
    session.flush()
    return run.id, rn, story


def test_correcao_cria_rn_nova_que_supera_a_original(session):
    run_id, original, story = _cenario(session)

    nova = criar_correcao(
        session, run_id, "RN-001", {"texto": "regra correta", "fonte": "contestação Q-01"}
    )

    assert nova.code == "RN-002"
    assert nova.status == RuleStatus.aprovada
    assert nova.supersedes_id == original.id
    assert "RN-001" in (nova.motivo or "")


def test_original_vira_superseded_e_nao_e_apagada(session):
    run_id, original, _ = _cenario(session)
    criar_correcao(session, run_id, "RN-001", {"texto": "corrigida", "fonte": "Q-01"})
    session.refresh(original)
    assert original.status == RuleStatus.superseded
    assert original.text == "regra errada"  # preservada, nunca apagada/editada


def test_historia_derivada_fica_stale(session):
    run_id, _, story = _cenario(session)
    criar_correcao(session, run_id, "RN-001", {"texto": "corrigida", "fonte": "Q-01"})
    session.refresh(story)
    assert story.stale is True


def test_correcao_exige_rn_contestada(session):
    run_id, _, _ = _cenario(session, status=RuleStatus.aprovada)
    with pytest.raises(ValueError, match="contestada"):
        criar_correcao(session, run_id, "RN-001", {"texto": "x", "fonte": "Q-01"})


def test_correcao_gera_auditoria(session):
    run_id, _, _ = _cenario(session)
    criar_correcao(session, run_id, "RN-001", {"texto": "corrigida", "fonte": "Q-01"})
    acoes = set(
        session.scalars(
            AuditLog.__table__.select().with_only_columns(AuditLog.action).where(
                AuditLog.run_id == run_id
            )
        )
    )
    assert {"corrigir", "superseded", "stale"} <= acoes
