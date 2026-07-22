"""Tetos de orçamento por run (Fase 8): decisão pura + no-op quando desligado.

A consulta ao banco é coberta indiretamente; aqui exercitamos a decisão pura
(`avaliar_orcamento`) com os limites da config alternados por monkeypatch, e a
mensagem clara que a UI recebe no 402.
"""

import pytest

from src import budget
from src.budget import BudgetExceeded, avaliar_orcamento, check_budget


def test_desligado_nao_levanta(monkeypatch):
    monkeypatch.setattr(budget.settings, "max_tokens_per_run", 0)
    monkeypatch.setattr(budget.settings, "max_usd_per_run", 0.0)
    avaliar_orcamento(1, 10_000_000, 999.0)  # não levanta
    check_budget("1")  # no-op, nem toca no banco


def test_estoura_tokens(monkeypatch):
    monkeypatch.setattr(budget.settings, "max_tokens_per_run", 1000)
    monkeypatch.setattr(budget.settings, "max_usd_per_run", 0.0)
    with pytest.raises(BudgetExceeded) as ei:
        avaliar_orcamento(7, 1000, 0.0)
    assert ei.value.kind == "tokens"
    assert "abortado" in str(ei.value).lower()


def test_estoura_usd(monkeypatch):
    monkeypatch.setattr(budget.settings, "max_tokens_per_run", 0)
    monkeypatch.setattr(budget.settings, "max_usd_per_run", 5.0)
    with pytest.raises(BudgetExceeded) as ei:
        avaliar_orcamento(7, 10, 5.5)
    assert ei.value.kind == "usd"


def test_abaixo_do_teto_passa(monkeypatch):
    monkeypatch.setattr(budget.settings, "max_tokens_per_run", 1000)
    monkeypatch.setattr(budget.settings, "max_usd_per_run", 5.0)
    avaliar_orcamento(7, 999, 4.99)  # não levanta


def test_check_budget_ignora_session_id_nao_numerico(monkeypatch):
    monkeypatch.setattr(budget.settings, "max_tokens_per_run", 1)
    check_budget("24-e3")  # thread_id do grafo, não run_id → no-op
    check_budget(None)
