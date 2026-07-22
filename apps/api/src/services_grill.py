"""Persistência de domínio do Grill Me (E2): sessão, Q&A e dossiê.

Antes, o histórico da entrevista e o dossiê viviam só no estado do
checkpointer (LangGraph). Aqui eles viram registros de primeira classe
(`grill_sessions`, `grill_qa`, `runs.dossie`), consultáveis e auditados —
o que o PRD §4/§5 pede. As funções são idempotentes o suficiente para o
padrão de resume do grafo (cada rodada grava seu Q&A uma vez).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import GrillQA, GrillSession, Run
from .services_regras import _audit, default_user


def abrir_sessao(session: Session, run_id: int) -> GrillSession:
    """Cria (ou reusa) a GrillSession do run."""
    gs = session.scalar(
        select(GrillSession).where(GrillSession.run_id == run_id)
    )
    if gs is None:
        gs = GrillSession(run_id=run_id, status="ativa")
        session.add(gs)
        session.flush()
    return gs


def registrar_qa(
    session: Session,
    run_id: int,
    perguntas: list[dict],
    respostas: dict[str, str],
) -> None:
    """Grava as perguntas/respostas de UMA rodada na grill_qa."""
    gs = abrir_sessao(session, run_id)
    for p in perguntas:
        session.add(
            GrillQA(
                grill_session_id=gs.id,
                question=p.get("texto", ""),
                answer=respostas.get(p.get("id", "")),
                item_checklist=p.get("item_checklist"),
            )
        )
    session.commit()


def fechar_sessao_com_dossie(session: Session, run_id: int, dossie: str) -> None:
    """Persiste o dossiê em `runs`, fecha a sessão e audita."""
    run = session.get(Run, run_id)
    if run is None:
        return
    actor = default_user(session)
    antes = {"dossie": bool(run.dossie)}
    run.dossie = dossie
    gs = abrir_sessao(session, run_id)
    gs.status = "concluida"
    _audit(
        session,
        actor_id=actor.id,
        action="dossie",
        entity="run",
        entity_id=run_id,
        before=antes,
        after={"dossie": True, "chars": len(dossie)},
        run_id=run_id,
    )
    session.commit()
