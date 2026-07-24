"""Grafo E5 (LangGraph): arquiteto de stack ∥ designer de testes.

PRD §4/E5 — os dois nós rodam em RAMOS PARALELOS (fan-out após aprovação das
histórias, fan-in antes de persistir):

    START → arquiteto ∥ designer → persistir → END

Escrevem chaves distintas do estado (`adr` / `cenarios`), então o fan-in não
precisa de reducer. No trace do Langfuse aparecem como dois ramos irmãos.
Sem HITL: E5 não tem gate humano (os gates são E3/E4).
"""

from __future__ import annotations

from functools import lru_cache
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from sqlalchemy import select

from ..agents.arquitetura import desenhar_cenarios, propor_stack
from ..db import SessionLocal
from ..models import Adr, Epic, Run, Story, TestScenario
from ..services_regras import (
    historias_aprovadas,
    persistir_e5,
    regras_aprovadas,
)
from .pipeline import _checkpointer, dossie_do_run


class E5State(TypedDict):
    project_id: int
    run_id: int
    dossie: str
    regras: list[dict]
    historias: list[dict]
    adr: dict
    cenarios: list[dict]


def _sid(state: E5State) -> str:
    return str(state["run_id"])


# ─── Ramos paralelos ──────────────────────────────────────────────────────
def _arquiteto(state: E5State) -> dict:
    adr = propor_stack(
        state["project_id"],
        state["dossie"],
        state["regras"],
        state["historias"],
        _sid(state),
    )
    return {"adr": adr.model_dump()}


def _designer(state: E5State) -> dict:
    grupos = []
    for h in state["historias"]:
        cen = desenhar_cenarios(h, _sid(state))
        grupos.append({"story_id": h["id"], "cenarios": [c.model_dump() for c in cen.cenarios]})
    return {"cenarios": grupos}


def _persistir(state: E5State) -> dict:
    session = SessionLocal()
    try:
        persistir_e5(session, state["run_id"], state["adr"], state["cenarios"])
    finally:
        session.close()
    return {}


@lru_cache(maxsize=1)
def _graph():
    b = StateGraph(E5State)
    b.add_node("arquiteto", _arquiteto)
    b.add_node("designer", _designer)
    b.add_node("persistir", _persistir)
    # fan-out paralelo a partir do START
    b.add_edge(START, "arquiteto")
    b.add_edge(START, "designer")
    # fan-in: persistir só roda quando os dois ramos terminam
    b.add_edge("arquiteto", "persistir")
    b.add_edge("designer", "persistir")
    b.add_edge("persistir", END)
    return b.compile(checkpointer=_checkpointer())


def _thread(run_id: int) -> dict:
    return {"configurable": {"thread_id": f"{run_id}-e5"}}


# ─── Serviço (usado pelos endpoints) ──────────────────────────────────────
def _estado(run_id: int) -> dict:
    session = SessionLocal()
    try:
        adr = session.scalar(select(Adr).where(Adr.run_id == run_id))
        adr_out = (
            {
                "title": adr.title,
                "context": adr.context,
                "options": adr.options,
                "decision": adr.decision,
                "consequences": adr.consequences,
            }
            if adr
            else None
        )
        historias = []
        for story in session.scalars(
            select(Story).join(Epic).where(Epic.run_id == run_id).order_by(Story.id)
        ):
            cenarios = [
                {"kind": c.kind, "gherkin": c.gherkin}
                for c in session.scalars(
                    select(TestScenario)
                    .where(TestScenario.story_id == story.id)
                    .order_by(TestScenario.id)
                )
            ]
            if cenarios:
                historias.append(
                    {"story_id": story.id, "title": story.title, "cenarios": cenarios}
                )
    finally:
        session.close()
    return {
        "run_id": run_id,
        "status": "concluido" if adr_out else "pendente",
        "adr": adr_out,
        "historias": historias,
    }


def preparar_e5(run_id: int) -> E5State:
    """Valida o run e monta o estado inicial. Levanta ValueError se não está pronto.

    Separado de `start_e5` porque a rota valida de forma síncrona (409
    imediato) e só então despacha o trabalho longo em background.
    """
    dossie = dossie_do_run(run_id)
    if not dossie:
        raise ValueError("dossiê ausente — rode o Grill Me (E2) antes")
    session = SessionLocal()
    try:
        run = session.get(Run, run_id)
        if run is None:
            raise ValueError("run não encontrado")
        project_id = run.project_id
        regras = regras_aprovadas(session, run_id)
        historias = historias_aprovadas(session, run_id)
    finally:
        session.close()
    if not historias:
        raise ValueError("nenhuma história aprovada — aprove histórias na E4 antes")

    initial: E5State = {
        "project_id": project_id,
        "run_id": run_id,
        "dossie": dossie,
        "regras": regras,
        "historias": historias,
        "adr": {},
        "cenarios": [],
    }
    return initial


def start_e5(run_id: int) -> dict:
    """Roda os dois ramos (arquiteto ∥ designer) e persiste ADR + cenários."""
    _graph().invoke(preparar_e5(run_id), _thread(run_id))
    return _estado(run_id)


def get_e5(run_id: int) -> dict:
    return _estado(run_id)
