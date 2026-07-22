"""Tetos duros de orçamento por run — Fase 8 / PRD §6-Segurança.

Reaproveita as métricas da Fase 7 (`llm_calls`): antes de cada chamada de LLM,
soma o que o run já gastou (tokens e USD) e, se passou de `MAX_TOKENS_PER_RUN`
ou `MAX_USD_PER_RUN`, aborta com `BudgetExceeded`. A exceção sobe até um handler
da API, que marca o run como `abortado` e devolve 402 com mensagem clara à UI.

Ambos os limites em 0 = desligado (dev). A checagem é pré-chamada: quando o
gasto acumulado cruza o teto, a PRÓXIMA chamada do run é bloqueada.
"""

from __future__ import annotations

from sqlalchemy import func, select

from .config import settings
from .models import LlmCall
from .observability import get_logger

log = get_logger("budget")


class BudgetExceeded(Exception):
    """Run estourou um teto de orçamento (tokens ou USD)."""

    def __init__(self, run_id: int | None, kind: str, spent: float, limit: float):
        self.run_id = run_id
        self.kind = kind
        self.spent = spent
        self.limit = limit
        unidade = "tokens" if kind == "tokens" else "USD"
        super().__init__(
            f"orçamento do run {run_id} excedido: {spent:.4g} {unidade} "
            f"≥ limite de {limit:.4g} {unidade}. Run abortado."
        )


def avaliar_orcamento(run_id: int | None, tokens: int, custo: float) -> None:
    """Decisão pura: levanta BudgetExceeded se o gasto cruzou um teto ligado."""
    lim_tok = settings.max_tokens_per_run
    lim_usd = settings.max_usd_per_run
    if lim_tok > 0 and tokens >= lim_tok:
        raise BudgetExceeded(run_id, "tokens", tokens, lim_tok)
    if lim_usd > 0 and custo >= lim_usd:
        raise BudgetExceeded(run_id, "usd", custo, lim_usd)


def check_budget(session_id: str | None) -> None:
    """Levanta BudgetExceeded se o run já cruzou um teto. No-op se desligado."""
    if settings.max_tokens_per_run <= 0 and settings.max_usd_per_run <= 0:
        return
    if session_id is None:
        return
    try:
        run_id = int(session_id)
    except ValueError:
        return

    from .db import SessionLocal

    session = SessionLocal()
    try:
        tokens, custo = session.execute(
            select(
                func.coalesce(func.sum(LlmCall.tokens_in + LlmCall.tokens_out), 0),
                func.coalesce(func.sum(LlmCall.cost_usd), 0.0),
            ).where(LlmCall.run_id == run_id)
        ).one()
    finally:
        session.close()

    avaliar_orcamento(run_id, int(tokens), float(custo))
