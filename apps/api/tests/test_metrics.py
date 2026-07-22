"""Métricas por estágio (Fase 7): custo, mapeamento nó→estágio e agregação.

Testes puros/determinísticos — sem LLM. A agregação usa a sessão do fixture
(savepoint), inserindo linhas de llm_calls e conferindo os totais por estágio.
"""

import pytest
from sqlalchemy.orm import Session

from src.db import engine
from src.metrics import (
    _run_id_from_session,
    cost_usd,
    metrics_agregado,
    metrics_por_run,
    stage_of,
)
from src.models import LlmCall, Project, Run


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


# ─── cálculo puro ──────────────────────────────────────────────────────────
def test_stage_of_mapeia_nos_conhecidos():
    assert stage_of("grill") == "E2"
    assert stage_of("extrator") == "E3"
    assert stage_of("analista") == "E4"
    assert stage_of("arquiteto") == "E5"
    assert stage_of("fatiador") == "E6"
    assert stage_of("inexistente") == "?"


def test_cost_usd_pro_e_flash():
    # pro: (0.55, 2.19) por 1M → 1M in + 1M out = 0.55 + 2.19
    assert cost_usd("deepseek-v4-pro", 1_000_000, 1_000_000) == pytest.approx(2.74)
    # flash mais barato que pro
    c_flash = cost_usd("deepseek-v4-flash", 1_000_000, 1_000_000)
    assert c_flash < 2.74


def test_cost_usd_modelo_desconhecido_e_zero():
    assert cost_usd("modelo-fantasma", 1000, 1000) == 0.0


def test_run_id_from_session():
    assert _run_id_from_session("24") == 24
    assert _run_id_from_session(None) is None
    assert _run_id_from_session("24-e3") is None  # thread_id não é run_id puro


# ─── agregação (lê do banco via savepoint) ─────────────────────────────────
def _run(session) -> int:
    p = Project(name="proj-m")
    session.add(p)
    session.flush()
    r = Run(project_id=p.id, stage="E3")
    session.add(r)
    session.flush()
    return r.id


def test_metrics_por_run_agrega_por_estagio(session):
    run_id = _run(session)
    session.add_all(
        [
            LlmCall(run_id=run_id, node="extrator", stage="E3", model="m",
                    tokens_in=100, tokens_out=50, cost_usd=0.01, latency_ms=1200),
            LlmCall(run_id=run_id, node="critico", stage="E3", model="m",
                    tokens_in=200, tokens_out=80, cost_usd=0.02, latency_ms=800),
            LlmCall(run_id=run_id, node="analista", stage="E4", model="m",
                    tokens_in=300, tokens_out=120, cost_usd=0.05, latency_ms=2000),
        ]
    )
    session.flush()

    m = metrics_por_run(session, run_id)
    por_stage = {e["stage"]: e for e in m["estagios"]}
    assert por_stage["E3"]["chamadas"] == 2  # 2 chamadas no E3 (proxy de iterações)
    assert por_stage["E3"]["tokens_in"] == 300
    assert por_stage["E3"]["latency_ms"] == 2000
    assert m["total"]["chamadas"] == 3
    assert m["total"]["cost_usd"] == pytest.approx(0.08)
    assert m["total"]["latency_ms"] == 4000


def test_metrics_agregado_soma_todos_os_runs(session):
    run_id = _run(session)
    session.add(
        LlmCall(run_id=run_id, node="grill", stage="E2", model="m",
                tokens_in=10, tokens_out=5, cost_usd=0.03, latency_ms=500)
    )
    session.flush()

    ag = metrics_agregado(session)
    assert any(e["stage"] == "E2" for e in ag["estagios"])
    assert any(r["run_id"] == run_id for r in ag["runs"])
    assert ag["total"]["cost_usd"] >= 0.03
