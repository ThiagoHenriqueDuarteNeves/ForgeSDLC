"""Grafo E6 (LangGraph): fatiador vertical.

    START → fatiar → (fecha? ou 3ª iteração → persistir ; senão → fatiar)
    persistir (grava slices + pacotes F-XXX.md) → END

Só histórias APROVADAS (E4) entram. O validador puro (agents/fatiador) recusa
fatia de camada única e história órfã, realimentando o fatiador (máx. 3).
Sem HITL: o gate de qualidade é o validador, não uma aprovação humana.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from sqlalchemy import select

from ..agents.fatiador import fatiar, injetar_cenarios, validar_fatias
from ..agents.schemas import MapaFatias
from ..config import settings
from ..db import SessionLocal
from ..models import Epic, Run, Slice, Story, TestScenario
from ..services_regras import historias_aprovadas, persistir_fatias
from .pipeline import _checkpointer, dossie_do_run

# Máx. de iterações de refatiamento, configurável por env (Fase 8).
MAX_ITER = settings.max_iter_per_stage


class FatiasState(TypedDict):
    project_id: int
    run_id: int
    dossie: str
    historias: list[dict]
    ids_validos: list[int]
    mapa: dict
    feedback: str
    iteracao: int


def _fatias_dir() -> str | None:
    """docs/fatias na raiz do repo (best-effort; None dentro do container)."""
    parents = Path(__file__).resolve().parents
    if len(parents) > 4:
        return str(parents[4] / "docs" / "fatias")
    return None


def _fatiar(state: FatiasState) -> dict:
    mapa = fatiar(
        state["project_id"],
        state["dossie"],
        state["historias"],
        str(state["run_id"]),
        feedback=state.get("feedback", ""),
    )
    feedback = validar_fatias(mapa, set(state["ids_validos"]))
    return {
        "mapa": mapa.model_dump(),
        "feedback": feedback,
        "iteracao": state["iteracao"] + 1,
    }


def _rota(state: FatiasState) -> str:
    if not state["feedback"] or state["iteracao"] >= MAX_ITER:
        return "persistir"
    return "fatiar"


def _persistir(state: FatiasState) -> dict:
    session = SessionLocal()
    try:
        mapa = MapaFatias.model_validate(state["mapa"])
        persistir_fatias(
            session,
            state["run_id"],
            [f.model_dump() for f in mapa.fatias],
            state["historias"],
            _fatias_dir(),
        )
    finally:
        session.close()
    return {}


@lru_cache(maxsize=1)
def _graph():
    b = StateGraph(FatiasState)
    b.add_node("fatiar", _fatiar)
    b.add_node("persistir", _persistir)
    b.add_edge(START, "fatiar")
    b.add_conditional_edges("fatiar", _rota, ["fatiar", "persistir"])
    b.add_edge("persistir", END)
    return b.compile(checkpointer=_checkpointer())


def _thread(run_id: int) -> dict:
    return {"configurable": {"thread_id": f"{run_id}-e6"}}


def _cenarios_map(session, run_id: int) -> dict[int, list[dict]]:
    """{story_id: [{kind, gherkin}]} — cenários atuais da E5 (para injetar)."""
    out: dict[int, list[dict]] = {}
    for cen in session.scalars(
        select(TestScenario)
        .join(Story)
        .join(Epic)
        .where(Epic.run_id == run_id)
        .order_by(TestScenario.id)
    ):
        out.setdefault(cen.story_id, []).append(
            {"kind": cen.kind, "gherkin": cen.gherkin}
        )
    return out


def _estado(run_id: int) -> dict:
    session = SessionLocal()
    try:
        cenarios = _cenarios_map(session, run_id)
        fatias = [
            {
                "code": s.code,
                "title": s.title,
                "status": s.status,
                "package_path": s.package_path,
                # Cenários montados na leitura: rodar a E5 depois reflete aqui.
                "package_md": injetar_cenarios(s.package_md or "", cenarios),
            }
            for s in session.scalars(
                select(Slice).where(Slice.run_id == run_id).order_by(Slice.code)
            )
        ]
    finally:
        session.close()
    return {
        "run_id": run_id,
        "status": "concluido" if fatias else "pendente",
        "fatias": fatias,
    }


def start_fatias(run_id: int) -> dict:
    """Roda o fatiador (E6): agrupa histórias aprovadas em fatias verticais."""
    dossie = dossie_do_run(run_id)
    if not dossie:
        raise ValueError("dossiê ausente — rode o Grill Me (E2) antes")
    session = SessionLocal()
    try:
        run = session.get(Run, run_id)
        if run is None:
            raise ValueError("run não encontrado")
        project_id = run.project_id
        historias = historias_aprovadas(session, run_id)
    finally:
        session.close()
    if not historias:
        raise ValueError("nenhuma história aprovada — aprove histórias na E4 antes")

    initial: FatiasState = {
        "project_id": project_id,
        "run_id": run_id,
        "dossie": dossie,
        "historias": historias,
        "ids_validos": [h["id"] for h in historias],
        "mapa": {},
        "feedback": "",
        "iteracao": 0,
    }
    _graph().invoke(initial, _thread(run_id))
    return _estado(run_id)


def get_fatias(run_id: int) -> dict:
    return _estado(run_id)
