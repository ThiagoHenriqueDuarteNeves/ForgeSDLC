"""Grafo LangGraph do pipeline (Fase 3: Grill Me) com checkpointer Postgres.

Fluxo HITL:
    START → gerar → (suficiente? → dossie ; senão → perguntar)
    perguntar → interrupt(perguntas) → [respostas] → (encerrar? → dossie ; senão → gerar)
    dossie → END

O padrão de dois nós (gerar/perguntar) evita re-gerar perguntas no resume:
o `interrupt` fica só no nó `perguntar`, que ao retomar devolve as respostas
sem repetir a chamada ao LLM do nó `gerar` (já checkpointado).

O estado é persistido pelo PostgresSaver, então matar a API no meio e subir
de novo retoma do mesmo ponto (prova do checkpointer — critério da Fase 3).
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any, TypedDict

from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from ..agents.grill import gerar_dossie, gerar_rodada
from ..config import settings
from ..db import SessionLocal
from ..models import Run, RunStatus
from ..services_grill import abrir_sessao, fechar_sessao_com_dossie, registrar_qa

MAX_RODADAS = 6


class GrillState(TypedDict):
    project_id: int
    run_id: int  # = thread_id; vira session_id no Langfuse (agrupa o run)
    historico: list[dict]
    cobertura: dict
    perguntas_pendentes: list[dict]
    cobertura_suficiente: bool
    encerrar: bool
    num_rodadas: int
    dossie: str | None


# ─── Nós ──────────────────────────────────────────────────────────────────
def _session_id(state: GrillState) -> str | None:
    rid = state.get("run_id")
    return str(rid) if rid else None


def _gerar(state: GrillState) -> dict:
    r = gerar_rodada(state["project_id"], state["historico"], _session_id(state))
    return {
        "cobertura": r.cobertura,
        "perguntas_pendentes": [p.model_dump() for p in r.perguntas],
        "cobertura_suficiente": r.cobertura_suficiente,
    }


def _perguntar(state: GrillState) -> dict:
    payload: Any = interrupt({"perguntas": state["perguntas_pendentes"]})
    respostas = (payload or {}).get("respostas", {})
    encerrar = bool((payload or {}).get("encerrar", False))
    nova_rodada = {"perguntas": state["perguntas_pendentes"], "respostas": respostas}
    # Persiste o Q&A desta rodada em domínio (grill_qa).
    session = SessionLocal()
    try:
        registrar_qa(session, state["run_id"], state["perguntas_pendentes"], respostas)
    finally:
        session.close()
    return {
        "historico": [*state["historico"], nova_rodada],
        "num_rodadas": state["num_rodadas"] + 1,
        "encerrar": encerrar,
    }


def _dossie(state: GrillState) -> dict:
    md = gerar_dossie(
        state["project_id"], state["historico"], state["cobertura"], _session_id(state)
    )
    # Persiste o dossiê em domínio (runs.dossie) e fecha a sessão do grill.
    session = SessionLocal()
    try:
        fechar_sessao_com_dossie(session, state["run_id"], md)
    finally:
        session.close()
    return {"dossie": md}


def _rota_apos_gerar(state: GrillState) -> str:
    if (
        state["encerrar"]
        or state["cobertura_suficiente"]
        or state["num_rodadas"] >= MAX_RODADAS
        or not state["perguntas_pendentes"]
    ):
        return "dossie"
    return "perguntar"


def _rota_apos_perguntar(state: GrillState) -> str:
    return "dossie" if state["encerrar"] else "gerar"


# ─── Checkpointer + grafo (singletons preguiçosos) ────────────────────────
def _conninfo() -> str:
    # PostgresSaver usa psycopg puro: sem o sufixo "+psycopg" do SQLAlchemy.
    return settings.database_url.replace("postgresql+psycopg://", "postgresql://")


@lru_cache(maxsize=1)
def _checkpointer() -> PostgresSaver:
    pool = ConnectionPool(
        conninfo=_conninfo(),
        max_size=10,
        kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
    )
    cp = PostgresSaver(pool)
    cp.setup()  # cria as tabelas do checkpointer (idempotente)
    return cp


@lru_cache(maxsize=1)
def _graph():
    b = StateGraph(GrillState)
    b.add_node("gerar", _gerar)
    b.add_node("perguntar", _perguntar)
    b.add_node("dossie", _dossie)
    b.add_edge(START, "gerar")
    b.add_conditional_edges("gerar", _rota_apos_gerar, ["perguntar", "dossie"])
    b.add_conditional_edges("perguntar", _rota_apos_perguntar, ["gerar", "dossie"])
    b.add_edge("dossie", END)
    return b.compile(checkpointer=_checkpointer())


# ─── Serviço (usado pelos endpoints) ──────────────────────────────────────
def _payload(run_id: int, result: dict) -> dict:
    interrupts = result.get("__interrupt__")
    if interrupts:
        return {
            "run_id": run_id,
            "status": "aguardando_respostas",
            "cobertura": result.get("cobertura", {}),
            "perguntas": interrupts[0].value["perguntas"],
            "dossie": None,
        }
    return {
        "run_id": run_id,
        "status": "concluido",
        "cobertura": result.get("cobertura", {}),
        "perguntas": [],
        "dossie": result.get("dossie"),
    }


def start_grill(project_id: int) -> dict:
    """Cria um run e roda o Grill Me até a primeira interrupção (perguntas)."""
    session = SessionLocal()
    try:
        run = Run(project_id=project_id, stage="E2", status=RunStatus.em_andamento)
        session.add(run)
        session.commit()
        run_id = run.id
        abrir_sessao(session, run_id)
        session.commit()
    finally:
        session.close()

    initial: GrillState = {
        "project_id": project_id,
        "run_id": run_id,
        "historico": [],
        "cobertura": {},
        "perguntas_pendentes": [],
        "cobertura_suficiente": False,
        "encerrar": False,
        "num_rodadas": 0,
        "dossie": None,
    }
    config = {"configurable": {"thread_id": str(run_id)}}
    result = _graph().invoke(initial, config)
    return _payload(run_id, result)


def answer_grill(run_id: int, respostas: dict, encerrar: bool = False) -> dict:
    """Retoma o grafo com as respostas da rodada."""
    config = {"configurable": {"thread_id": str(run_id)}}
    result = _graph().invoke(
        Command(resume={"respostas": respostas, "encerrar": encerrar}), config
    )
    return _payload(run_id, result)


def dossie_do_run(run_id: int) -> str | None:
    """Recupera o dossiê do run — de `runs.dossie` (domínio), com fallback ao
    estado do grafo para runs antigos (anteriores à persistência em domínio).

    É a entrada dos estágios E3/E4/E5, que reusam o mesmo run_id para que o
    trace do Langfuse agrupe E2→E5 na mesma sessão.
    """
    session = SessionLocal()
    try:
        run = session.get(Run, run_id)
        if run is not None and run.dossie:
            return run.dossie
    finally:
        session.close()
    config = {"configurable": {"thread_id": str(run_id)}}
    snap = _graph().get_state(config)
    return (snap.values or {}).get("dossie")


def get_grill(run_id: int) -> dict:
    """Estado atual do run (perguntas pendentes ou dossiê)."""
    config = {"configurable": {"thread_id": str(run_id)}}
    snap = _graph().get_state(config)
    values = snap.values or {}
    aguardando = bool(snap.next)  # há nó pendente => aguardando respostas
    return {
        "run_id": run_id,
        "status": "aguardando_respostas" if aguardando else "concluido",
        "cobertura": values.get("cobertura", {}),
        "perguntas": values.get("perguntas_pendentes", []) if aguardando else [],
        "dossie": values.get("dossie"),
    }
