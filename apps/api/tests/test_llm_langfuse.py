"""Gating do Langfuse no factory de LLM (src/llm.py).

Garante o contrato de duas pontas:
  - SEM chaves → `_run_config` é vazio (no-op): a API roda sem observabilidade.
  - COM handler → o config carrega o callback e agrupa o run pelo session_id
    (= run_id), atendendo à regra do CLAUDE.md (código sem trace não entra
    quando o Langfuse está ligado).
"""

from src import llm


def test_run_config_vazio_sem_chaves(monkeypatch):
    # Sem chaves configuradas, o handler é None e o config sai vazio.
    monkeypatch.setattr(llm, "_langfuse_handler", lambda: None)
    assert llm._run_config("grill", "42") == {}


def test_run_config_com_handler_agrupa_por_session(monkeypatch):
    sentinel = object()
    monkeypatch.setattr(llm, "_langfuse_handler", lambda: sentinel)

    cfg = llm._run_config("grill", "42")

    assert cfg["callbacks"] == [sentinel]
    assert cfg["metadata"]["langfuse_session_id"] == "42"
    assert cfg["metadata"]["langfuse_tags"] == ["grill"]


def test_run_config_sem_session_id_nao_quebra(monkeypatch):
    monkeypatch.setattr(llm, "_langfuse_handler", lambda: object())
    cfg = llm._run_config("grill", None)
    assert "langfuse_session_id" not in cfg["metadata"]


def test_handler_none_quando_chaves_vazias(monkeypatch):
    # Contrato do gating direto na fonte: chaves vazias ⇒ None.
    monkeypatch.setattr(llm.settings, "langfuse_public_key", "")
    monkeypatch.setattr(llm.settings, "langfuse_secret_key", "")
    llm._langfuse_handler.cache_clear()
    assert llm._langfuse_handler() is None
    llm._langfuse_handler.cache_clear()
