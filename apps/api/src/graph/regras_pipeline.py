"""Subgrafo E3 (LangGraph): extração e refino de regras de negócio.

Fluxo (PRD §4/E3):
    START → extrair_1 ∥ extrair_2 ∥ extrair_3   (self-consistency, fan-out)
          → consolidar (dedup + confiança) → criticar
    criticar → (todas aprovadas? ou 3ª iteração → persistir ; senão → refinar)
    refinar → criticar
    persistir (grava RNs propostas) → aguardar_aprovacao (interrupt)
          → aplicar (aprovar/rejeitar/contestar) → END

O gate humano é o `interrupt` em `aguardar_aprovacao`: RNs ficam propostas até
o PO decidir; só depois `aplicar` transiciona o status. E4 lê apenas RNs
aprovadas, então a aprovação bloqueia comprovadamente o avanço.

Padrão de dois nós (persistir↑ / aguardar↓): a escrita das RNs acontece ANTES
do interrupt, para não repetir no resume (o mesmo cuidado do grafo do Grill Me).
"""

from __future__ import annotations

import operator
from functools import lru_cache
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from sqlalchemy import select

from ..agents.regras import consolidar, criticar, extrair_regras, refinar
from ..agents.schemas import ConjuntoRegras, ExtracaoRegras, RelatorioCritico
from ..db import SessionLocal
from ..models import BusinessRule, Run
from ..services_regras import aplicar_decisoes_regras, persistir_regras
from .pipeline import _checkpointer, dossie_do_run

MAX_ITER = 3


class RegrasState(TypedDict):
    project_id: int
    run_id: int
    dossie: str
    extracoes: Annotated[list[dict], operator.add]  # fan-in das 3 extrações
    conjunto: list[dict]
    relatorio: dict
    iteracao: int
    decisoes: dict


def _sid(state: RegrasState) -> str:
    return str(state["run_id"])


# ─── Nós ──────────────────────────────────────────────────────────────────
def _extrair(state: RegrasState) -> dict:
    ext = extrair_regras(state["project_id"], state["dossie"], _sid(state))
    return {"extracoes": [ext.model_dump()]}


def _consolidar(state: RegrasState) -> dict:
    extracoes = [ExtracaoRegras.model_validate(e) for e in state["extracoes"]]
    conj = consolidar(extracoes, _sid(state))
    return {"conjunto": [r.model_dump() for r in conj.regras], "iteracao": 0}


def _criticar(state: RegrasState) -> dict:
    conj = ConjuntoRegras(regras=state["conjunto"])
    rel = criticar(conj, _sid(state))
    return {"relatorio": rel.model_dump()}


def _rota_critico(state: RegrasState) -> str:
    rel = RelatorioCritico.model_validate(state["relatorio"])
    if rel.todas_aprovadas or state["iteracao"] >= MAX_ITER - 1:
        return "persistir"
    return "refinar"


def _refinar(state: RegrasState) -> dict:
    conj = ConjuntoRegras(regras=state["conjunto"])
    rel = RelatorioCritico.model_validate(state["relatorio"])
    novo = refinar(conj, rel, _sid(state))
    return {
        "conjunto": [r.model_dump() for r in novo.regras],
        "iteracao": state["iteracao"] + 1,
    }


def _persistir(state: RegrasState) -> dict:
    session = SessionLocal()
    try:
        persistir_regras(session, state["run_id"], state["conjunto"])
    finally:
        session.close()
    return {}


def _aguardar(state: RegrasState) -> dict:
    payload = interrupt({"aguardando": "aprovacao_regras"})
    return {"decisoes": (payload or {}).get("decisoes", {})}


def _aplicar(state: RegrasState) -> dict:
    session = SessionLocal()
    try:
        aplicar_decisoes_regras(session, state["run_id"], state["decisoes"])
    finally:
        session.close()
    return {}


# ─── Grafo (singleton preguiçoso) ─────────────────────────────────────────
@lru_cache(maxsize=1)
def _graph():
    b = StateGraph(RegrasState)
    for nome in ("extrair_1", "extrair_2", "extrair_3"):
        b.add_node(nome, _extrair)
    b.add_node("consolidar", _consolidar)
    b.add_node("criticar", _criticar)
    b.add_node("refinar", _refinar)
    b.add_node("persistir", _persistir)
    b.add_node("aguardar", _aguardar)
    b.add_node("aplicar", _aplicar)

    for nome in ("extrair_1", "extrair_2", "extrair_3"):
        b.add_edge(START, nome)
        b.add_edge(nome, "consolidar")
    b.add_edge("consolidar", "criticar")
    b.add_conditional_edges("criticar", _rota_critico, ["refinar", "persistir"])
    b.add_edge("refinar", "criticar")
    b.add_edge("persistir", "aguardar")
    b.add_edge("aguardar", "aplicar")
    b.add_edge("aplicar", END)
    return b.compile(checkpointer=_checkpointer())


def _thread(run_id: int) -> dict:
    # thread próprio do E3 (separado do Grill Me), mesmo run_id p/ o Langfuse.
    return {"configurable": {"thread_id": f"{run_id}-e3"}}


# ─── Serviço (usado pelos endpoints) ──────────────────────────────────────
def _estado(run_id: int) -> dict:
    """Lê as RNs do banco + se o grafo aguarda aprovação."""
    session = SessionLocal()
    try:
        rns = list(
            session.scalars(
                select(BusinessRule)
                .where(BusinessRule.run_id == run_id)
                .order_by(BusinessRule.code)
            )
        )
        regras = [
            {
                "code": r.code,
                "text": r.text,
                "fonte": r.fonte,
                "status": r.status,
                "id": r.id,
            }
            for r in rns
        ]
    finally:
        session.close()
    snap = _graph().get_state(_thread(run_id))
    aguardando = bool(snap.next)
    return {
        "run_id": run_id,
        "status": "aguardando_aprovacao" if aguardando else "concluido",
        "regras": regras,
    }


def start_regras(run_id: int) -> dict:
    """Roda o subgrafo E3 até o interrupt de aprovação; persiste as RNs."""
    dossie = dossie_do_run(run_id)
    if not dossie:
        raise ValueError("dossiê ainda não gerado para este run (rode o Grill Me)")
    session = SessionLocal()
    try:
        run = session.get(Run, run_id)
        if run is None:
            raise ValueError("run não encontrado")
        project_id = run.project_id
    finally:
        session.close()

    initial: RegrasState = {
        "project_id": project_id,
        "run_id": run_id,
        "dossie": dossie,
        "extracoes": [],
        "conjunto": [],
        "relatorio": {},
        "iteracao": 0,
        "decisoes": {},
    }
    _graph().invoke(initial, _thread(run_id))
    return _estado(run_id)


def aprovar_regras(run_id: int, decisoes: dict[str, str]) -> dict:
    """Retoma o grafo com as decisões (aprovar/rejeitar/contestar) por RN."""
    _graph().invoke(Command(resume={"decisoes": decisoes}), _thread(run_id))
    return _estado(run_id)


def get_regras(run_id: int) -> dict:
    return _estado(run_id)
