"""Grafo E4 (LangGraph): analista de histórias.

Fluxo (PRD §4/E4):
    START → gerar → (matriz fecha? ou 3ª iteração → persistir ; senão → gerar)
    persistir (grava épicos/histórias/matriz) → aguardar (interrupt) → aplicar → END

A validação da matriz RN↔US é pura (agents/historias.py): o loop de
auto-refinamento repassa ao gerador o feedback (RNs órfãs / histórias sem RN)
até fechar ou esgotar as iterações. Só RNs APROVADAS na E3 entram — logo a
E4 não avança sem a aprovação humana da E3.
"""

from __future__ import annotations

from functools import lru_cache
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from sqlalchemy import select

from ..agents.historias import gerar_historias, validar_matriz
from ..config import settings
from ..db import SessionLocal
from ..models import BusinessRule, Epic, Run, Story, StoryRule
from ..services_regras import (
    aplicar_decisoes_historias,
    persistir_historias,
    regras_aprovadas,
)
from .pipeline import _checkpointer, dossie_do_run

# Máx. de iterações do auto-refino da matriz, configurável por env (Fase 8).
MAX_ITER = settings.max_iter_per_stage


class HistoriasState(TypedDict):
    project_id: int
    run_id: int
    dossie: str
    regras_aprovadas: list[dict]
    codigos: list[str]
    mapa: dict
    feedback: str
    iteracao: int
    decisoes: dict


def _sid(state: HistoriasState) -> str:
    return str(state["run_id"])


def _gerar(state: HistoriasState) -> dict:
    mapa = gerar_historias(
        state["project_id"],
        state["dossie"],
        state["regras_aprovadas"],
        _sid(state),
        feedback=state.get("feedback", ""),
    )
    feedback = validar_matriz(mapa, set(state["codigos"]))
    return {
        "mapa": mapa.model_dump(),
        "feedback": feedback,
        "iteracao": state["iteracao"] + 1,
    }


def _rota_gerar(state: HistoriasState) -> str:
    if not state["feedback"] or state["iteracao"] >= MAX_ITER:
        return "persistir"
    return "gerar"


def _persistir(state: HistoriasState) -> dict:
    session = SessionLocal()
    try:
        persistir_historias(session, state["run_id"], state["mapa"])
    finally:
        session.close()
    return {}


def _aguardar(state: HistoriasState) -> dict:
    payload = interrupt({"aguardando": "aprovacao_historias"})
    return {"decisoes": (payload or {}).get("decisoes", {})}


def _aplicar(state: HistoriasState) -> dict:
    session = SessionLocal()
    try:
        aplicar_decisoes_historias(session, state["run_id"], state["decisoes"])
    finally:
        session.close()
    return {}


@lru_cache(maxsize=1)
def _graph():
    b = StateGraph(HistoriasState)
    b.add_node("gerar", _gerar)
    b.add_node("persistir", _persistir)
    b.add_node("aguardar", _aguardar)
    b.add_node("aplicar", _aplicar)
    b.add_edge(START, "gerar")
    b.add_conditional_edges("gerar", _rota_gerar, ["gerar", "persistir"])
    b.add_edge("persistir", "aguardar")
    b.add_edge("aguardar", "aplicar")
    b.add_edge("aplicar", END)
    return b.compile(checkpointer=_checkpointer())


def _thread(run_id: int) -> dict:
    return {"configurable": {"thread_id": f"{run_id}-e4"}}


def _estado(run_id: int) -> dict:
    session = SessionLocal()
    try:
        epicos = list(
            session.scalars(select(Epic).where(Epic.run_id == run_id).order_by(Epic.id))
        )
        historias = []
        for story in session.scalars(
            select(Story).join(Epic).where(Epic.run_id == run_id).order_by(Story.id)
        ):
            rn_codes = list(
                session.scalars(
                    select(BusinessRule.code)
                    .join(StoryRule, StoryRule.business_rule_id == BusinessRule.id)
                    .where(StoryRule.story_id == story.id)
                    .order_by(BusinessRule.code)
                )
            )
            historias.append(
                {
                    "id": story.id,
                    "epic_id": story.epic_id,
                    "title": story.title,
                    "gherkin": story.gherkin,
                    "status": story.status,
                    "rn_codes": rn_codes,
                }
            )
        epicos_out = [
            {"id": e.id, "title": e.title, "description": e.description} for e in epicos
        ]
    finally:
        session.close()
    snap = _graph().get_state(_thread(run_id))
    aguardando = bool(snap.next)
    return {
        "run_id": run_id,
        "status": "aguardando_aprovacao" if aguardando else "concluido",
        "epicos": epicos_out,
        "historias": historias,
    }


def start_historias(run_id: int) -> dict:
    """Roda a E4 (analista) até o interrupt de aprovação; persiste histórias."""
    dossie = dossie_do_run(run_id)
    if not dossie:
        raise ValueError("dossiê ausente — rode o Grill Me (E2) antes")
    session = SessionLocal()
    try:
        run = session.get(Run, run_id)
        if run is None:
            raise ValueError("run não encontrado")
        project_id = run.project_id
        aprovadas = regras_aprovadas(session, run_id)
    finally:
        session.close()
    if not aprovadas:
        raise ValueError("nenhuma RN aprovada — aprove regras na E3 antes da E4")

    initial: HistoriasState = {
        "project_id": project_id,
        "run_id": run_id,
        "dossie": dossie,
        "regras_aprovadas": aprovadas,
        "codigos": [r["code"] for r in aprovadas],
        "mapa": {},
        "feedback": "",
        "iteracao": 0,
        "decisoes": {},
    }
    _graph().invoke(initial, _thread(run_id))
    return _estado(run_id)


def aprovar_historias(run_id: int, decisoes: dict[str, str]) -> dict:
    """Retoma o grafo com aprovar/rejeitar por história (chave = id da história)."""
    _graph().invoke(Command(resume={"decisoes": decisoes}), _thread(run_id))
    return _estado(run_id)


def get_historias(run_id: int) -> dict:
    return _estado(run_id)
