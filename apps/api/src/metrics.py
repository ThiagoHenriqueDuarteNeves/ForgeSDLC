"""Métricas por estágio do pipeline — Fase 7 / PRD §6-Observabilidade.

Uma linha por chamada de LLM é gravada em `llm_calls` a partir do único ponto
de saída tipada (`llm.structured_call`). Daqui saem:
  - o cálculo de custo (tokens × preço do modelo, `cost_usd`);
  - o mapeamento nó→estágio (E2..E6);
  - o registro best-effort (nunca derruba o pipeline);
  - a agregação por estágio/run e agregada, que responde na UI
    "quanto custou este run e onde foi o tempo".

Preço vem de `settings.llm_prices_json` (override) ou de `DEFAULT_PRICES`.
"""

from __future__ import annotations

import json

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import settings
from .models import LlmCall
from .observability import bind_run, get_logger

log = get_logger("metrics")

# nó do grafo → estágio do SDLC (PRD §4).
NODE_TO_STAGE: dict[str, str] = {
    "grill": "E2",
    "extrator": "E3",
    "consolidador": "E3",
    "critico": "E3",
    "refinador": "E3",
    "analista": "E4",
    "arquiteto": "E5",
    "designer": "E5",
    "fatiador": "E6",
}

# Preço em USD por 1M tokens: {modelo: (entrada, saida)}. Ajustável por env
# (LLM_PRICES_JSON). Valores default plausíveis para os modelos DeepSeek V4.
DEFAULT_PRICES: dict[str, tuple[float, float]] = {
    "deepseek-v4-pro": (0.55, 2.19),
    "deepseek-v4-flash": (0.14, 0.28),
}


def _prices() -> dict[str, tuple[float, float]]:
    if not settings.llm_prices_json:
        return DEFAULT_PRICES
    try:
        raw = json.loads(settings.llm_prices_json)
        return {m: (float(v[0]), float(v[1])) for m, v in raw.items()}
    except (json.JSONDecodeError, ValueError, KeyError, TypeError):
        log.warning("llm_prices_json inválido; usando DEFAULT_PRICES")
        return DEFAULT_PRICES


def stage_of(node: str) -> str:
    return NODE_TO_STAGE.get(node, "?")


def cost_usd(model: str, tokens_in: int, tokens_out: int) -> float:
    """Custo da chamada. Modelo sem preço conhecido → 0.0 (com aviso)."""
    prices = _prices()
    if model not in prices:
        log.warning("modelo sem preço configurado", model=model)
        return 0.0
    pin, pout = prices[model]
    return (tokens_in * pin + tokens_out * pout) / 1_000_000


def _run_id_from_session(session_id: str | None) -> int | None:
    """session_id do Langfuse = str(run_id). Ignora threads não-numéricas."""
    if session_id is None:
        return None
    try:
        return int(session_id)
    except ValueError:
        return None


def record_llm_call(
    *,
    node: str,
    session_id: str | None,
    model: str,
    tokens_in: int,
    tokens_out: int,
    latency_ms: int,
) -> None:
    """Grava a métrica da chamada (best-effort) e emite o log estruturado.

    NUNCA propaga exceção: observabilidade não pode derrubar o pipeline. Abre
    a própria sessão (o `structured_call` não tem uma) e comita isolado.
    """
    run_id = _run_id_from_session(session_id)
    stage = stage_of(node)
    custo = cost_usd(model, tokens_in, tokens_out)

    bind_run(run_id, stage=stage, node=node)
    log.info(
        "llm_call",
        model=model,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost_usd=round(custo, 6),
        latency_ms=latency_ms,
    )

    from .db import SessionLocal

    session = SessionLocal()
    try:
        session.add(
            LlmCall(
                run_id=run_id,
                node=node,
                stage=stage,
                model=model,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                cost_usd=custo,
                latency_ms=latency_ms,
            )
        )
        session.commit()
    except Exception:  # noqa: BLE001 — best-effort: só logamos e seguimos.
        session.rollback()
        log.warning("falha ao gravar llm_call", node=node, run_id=run_id)
    finally:
        session.close()


# ─── Agregações para a UI ──────────────────────────────────────────────────
def _linha_estagio(row) -> dict:
    return {
        "stage": row.stage,
        "chamadas": row.chamadas,
        "tokens_in": row.tokens_in or 0,
        "tokens_out": row.tokens_out or 0,
        "cost_usd": float(row.cost_usd or 0.0),
        "latency_ms": row.latency_ms or 0,
    }


def metrics_por_run(session: Session, run_id: int) -> dict:
    """Quebra por estágio + totais de um run (custo e tempo por etapa)."""
    rows = session.execute(
        select(
            LlmCall.stage,
            func.count().label("chamadas"),
            func.sum(LlmCall.tokens_in).label("tokens_in"),
            func.sum(LlmCall.tokens_out).label("tokens_out"),
            func.sum(LlmCall.cost_usd).label("cost_usd"),
            func.sum(LlmCall.latency_ms).label("latency_ms"),
        )
        .where(LlmCall.run_id == run_id)
        .group_by(LlmCall.stage)
        .order_by(LlmCall.stage)
    ).all()
    estagios = [_linha_estagio(r) for r in rows]
    return {
        "run_id": run_id,
        "estagios": estagios,
        "total": _totais(estagios),
    }


def metrics_agregado(session: Session) -> dict:
    """Totais globais + por estágio + por run (visão agregada da UI)."""
    por_estagio = [
        _linha_estagio(r)
        for r in session.execute(
            select(
                LlmCall.stage,
                func.count().label("chamadas"),
                func.sum(LlmCall.tokens_in).label("tokens_in"),
                func.sum(LlmCall.tokens_out).label("tokens_out"),
                func.sum(LlmCall.cost_usd).label("cost_usd"),
                func.sum(LlmCall.latency_ms).label("latency_ms"),
            )
            .group_by(LlmCall.stage)
            .order_by(LlmCall.stage)
        ).all()
    ]
    por_run = [
        {
            "run_id": r.run_id,
            "chamadas": r.chamadas,
            "cost_usd": float(r.cost_usd or 0.0),
            "latency_ms": r.latency_ms or 0,
        }
        for r in session.execute(
            select(
                LlmCall.run_id,
                func.count().label("chamadas"),
                func.sum(LlmCall.cost_usd).label("cost_usd"),
                func.sum(LlmCall.latency_ms).label("latency_ms"),
            )
            .where(LlmCall.run_id.is_not(None))
            .group_by(LlmCall.run_id)
            .order_by(LlmCall.run_id.desc())
        ).all()
    ]
    return {
        "estagios": por_estagio,
        "runs": por_run,
        "total": _totais(por_estagio),
    }


def _totais(estagios: list[dict]) -> dict:
    return {
        "chamadas": sum(e["chamadas"] for e in estagios),
        "tokens_in": sum(e["tokens_in"] for e in estagios),
        "tokens_out": sum(e["tokens_out"] for e in estagios),
        "cost_usd": sum(e["cost_usd"] for e in estagios),
        "latency_ms": sum(e["latency_ms"] for e in estagios),
    }
