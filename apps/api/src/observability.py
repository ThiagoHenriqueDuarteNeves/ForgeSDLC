"""Logging estruturado (structlog) em JSON — Fase 7 / PRD §6-Observabilidade.

Toda linha de log da API sai em JSON com timestamp ISO e os campos de contexto
ligados via `contextvars` (`run_id`, `stage`, `node`). O binding é feito com
`bind_run` nos pontos de entrada do pipeline (nós do grafo) e em `structured_call`,
de modo que qualquer log emitido durante a execução de um run já carrega o
`run_id` e o estágio — CLAUDE.md: código sem trace não entra.

Um único `configure_logging()` é idempotente e chamado na subida da API
(`main.py`) e pode ser chamado por scripts (ex.: `scripts/eval.py`).
"""

from __future__ import annotations

import logging

import structlog

_configured = False


def configure_logging(level: int = logging.INFO) -> None:
    """Configura structlog para emitir JSON com contextvars. Idempotente."""
    global _configured
    if _configured:
        return

    logging.basicConfig(format="%(message)s", level=level)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    _configured = True


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Logger estruturado. Garante configuração mesmo fora do ciclo da API."""
    configure_logging()
    return structlog.get_logger(name)


def bind_run(run_id: int | None = None, **fields) -> None:
    """Liga campos de contexto (run_id/stage/node) a todos os logs seguintes.

    Usa contextvars: o binding vale para a task/execução corrente. Ignora
    valores None para não poluir o log com chaves vazias.
    """
    data = {k: v for k, v in {"run_id": run_id, **fields}.items() if v is not None}
    if data:
        structlog.contextvars.bind_contextvars(**data)


def clear_run() -> None:
    """Limpa o contexto ligado (fim de request/execução)."""
    structlog.contextvars.clear_contextvars()
