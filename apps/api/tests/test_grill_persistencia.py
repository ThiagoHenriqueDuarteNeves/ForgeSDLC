"""Dívidas quitadas: dossiê e Q&A do Grill Me viram registros de domínio.

Prova que a sessão é criada/reusada, que o Q&A de cada rodada é gravado, e
que o dossiê é persistido em `runs.dossie` com a sessão fechada e auditada.
Transação externa com savepoint (os serviços dão commit interno).
"""

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db import engine
from src.models import AuditLog, GrillQA, GrillSession, Project, Run
from src.services_grill import (
    abrir_sessao,
    fechar_sessao_com_dossie,
    registrar_qa,
)


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


def _run(session) -> int:
    project = Project(name="proj-grill")
    session.add(project)
    session.flush()
    run = Run(project_id=project.id, stage="E2")
    session.add(run)
    session.flush()
    return run.id


def test_abrir_sessao_e_idempotente(session):
    run_id = _run(session)
    a = abrir_sessao(session, run_id)
    b = abrir_sessao(session, run_id)
    assert a.id == b.id  # não cria duas sessões para o mesmo run


def test_registrar_qa_grava_perguntas_e_respostas(session):
    run_id = _run(session)
    perguntas = [
        {"id": "Q-01", "texto": "Quem aprova?", "item_checklist": "2. Atores"},
        {"id": "Q-02", "texto": "Qual o prazo?", "item_checklist": "7. Restrições"},
    ]
    registrar_qa(session, run_id, perguntas, {"Q-01": "o admin", "Q-02": "30 dias"})

    gs = session.scalar(select(GrillSession).where(GrillSession.run_id == run_id))
    qa = list(session.scalars(select(GrillQA).where(GrillQA.grill_session_id == gs.id)))
    assert len(qa) == 2
    q1 = next(q for q in qa if q.question == "Quem aprova?")
    assert q1.answer == "o admin"
    assert q1.item_checklist == "2. Atores"


def test_fechar_persiste_dossie_fecha_sessao_e_audita(session):
    run_id = _run(session)
    fechar_sessao_com_dossie(session, run_id, "# Dossiê\nconteúdo")

    run = session.get(Run, run_id)
    assert run.dossie == "# Dossiê\nconteúdo"
    gs = session.scalar(select(GrillSession).where(GrillSession.run_id == run_id))
    assert gs.status == "concluida"
    acoes = set(
        session.scalars(
            select(AuditLog.action).where(
                AuditLog.run_id == run_id, AuditLog.entity == "run"
            )
        )
    )
    assert "dossie" in acoes
