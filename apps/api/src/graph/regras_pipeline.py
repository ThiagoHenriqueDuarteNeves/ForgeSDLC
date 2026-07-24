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

from ..agents.regras import (
    consolidar,
    criticar,
    extrair_regras,
    perguntar_contestacao,
    refinar,
    resolver_contestacao,
)
from ..agents.schemas import ConjuntoRegras, ExtracaoRegras, RelatorioCritico
from ..config import settings
from ..db import SessionLocal
from ..models import BusinessRule, RuleStatus, Run
from ..services_regras import (
    aplicar_decisoes_regras,
    criar_correcao,
    persistir_regras,
)
from .pipeline import _checkpointer, dossie_do_run

# Máx. de iterações crítico↔refinador, configurável por env (Fase 8).
MAX_ITER = settings.max_iter_per_stage


class RegrasState(TypedDict):
    project_id: int
    run_id: int
    dossie: str
    extracoes: Annotated[list[dict], operator.add]  # fan-in das 3 extrações
    conjunto: list[dict]
    relatorio: dict
    iteracao: int
    decisoes: dict
    motivos: dict


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
    return {
        "decisoes": (payload or {}).get("decisoes", {}),
        "motivos": (payload or {}).get("motivos", {}),
    }


def _aplicar(state: RegrasState) -> dict:
    session = SessionLocal()
    try:
        aplicar_decisoes_regras(
            session, state["run_id"], state["decisoes"], state.get("motivos", {})
        )
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
        code_por_id = {r.id: r.code for r in rns}
        regras = [
            {
                "code": r.code,
                "text": r.text,
                "fonte": r.fonte,
                "status": r.status,
                "id": r.id,
                "motivo": r.motivo,
                "supersedes": code_por_id.get(r.supersedes_id) if r.supersedes_id else None,
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


def preparar_regras(run_id: int) -> RegrasState:
    """Valida o run e monta o estado inicial. Levanta ValueError se não está pronto.

    Separado de `start_regras` porque a rota precisa validar de forma síncrona
    (para responder 409 na hora) e só então despachar o trabalho longo.
    """
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
        "motivos": {},
    }
    return initial


def start_regras(run_id: int) -> dict:
    """Roda o subgrafo E3 até o interrupt de aprovação; persiste as RNs."""
    _graph().invoke(preparar_regras(run_id), _thread(run_id))
    return _estado(run_id)


def aprovar_regras(
    run_id: int, decisoes: dict[str, str], motivos: dict[str, str] | None = None
) -> dict:
    """Retoma o grafo com as decisões (aprovar/rejeitar/contestar) por RN.

    `motivos` (code→texto) acompanha a contestação e é aplicado pelo nó
    `aplicar` junto com as decisões (uma só gravação, um só audit).
    """
    _graph().invoke(
        Command(resume={"decisoes": decisoes, "motivos": motivos or {}}),
        _thread(run_id),
    )
    return _estado(run_id)


def get_regras(run_id: int) -> dict:
    return _estado(run_id)


# ─── Contestação dirigida + supersede (PRD §4/E3.1, pós-E3) ───────────────
def _rn_contestada(session, run_id: int, code: str) -> BusinessRule:
    rn = session.scalar(
        select(BusinessRule).where(
            BusinessRule.run_id == run_id, BusinessRule.code == code
        )
    )
    if rn is None:
        raise ValueError(f"RN {code} não encontrada")
    if rn.status != RuleStatus.contestada:
        raise ValueError(f"RN {code} não está contestada (está {rn.status})")
    return rn


def contestacao_perguntas(run_id: int, code: str) -> dict:
    """Abre a rodada dirigida do Grill Me sobre a lacuna da RN contestada."""
    session = SessionLocal()
    try:
        run = session.get(Run, run_id)
        if run is None:
            raise ValueError("run não encontrado")
        rn = _rn_contestada(session, run_id, code)
        project_id, texto, motivo = run.project_id, rn.text, rn.motivo or ""
    finally:
        session.close()
    rodada = perguntar_contestacao(project_id, texto, motivo, str(run_id))
    return {
        "code": code,
        "texto": texto,
        "motivo": motivo,
        "perguntas": [p.model_dump() for p in rodada.perguntas],
    }


def resolver_contestacao_run(
    run_id: int, code: str, respostas: dict[str, str]
) -> dict:
    """Sintetiza a RN corrigida e aplica o supersede (append-only)."""
    session = SessionLocal()
    try:
        run = session.get(Run, run_id)
        if run is None:
            raise ValueError("run não encontrado")
        rn = _rn_contestada(session, run_id, code)
        project_id, texto, motivo = run.project_id, rn.text, rn.motivo or ""
    finally:
        session.close()
    nova = resolver_contestacao(project_id, texto, motivo, respostas, str(run_id))
    session = SessionLocal()
    try:
        criar_correcao(session, run_id, code, nova.model_dump())
    finally:
        session.close()
    return _estado(run_id)
