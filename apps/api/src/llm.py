"""Factory único de clientes de LLM + saída tipada com blindagem de 3 camadas.

REGRA (CLAUDE.md): nenhum outro módulo constrói cliente de LLM nem importa
SDK de provider direto. Tudo passa por aqui, parametrizado por env, para que
trocar de provider (DeepSeek → OpenAI → vLLM local) seja mudança de .env.

Blindagem de saída (PRD §3.1), já que o provider não garante JSON Schema
estrito:
  1. forced tool/function call com o schema Pydantic (`with_structured_output`)
  2. validação Pydantic (a própria with_structured_output valida)
  3. em falha, re-prompt com o erro anexado (máx. 2 tentativas)
"""

from __future__ import annotations

import json
import time
from functools import lru_cache
from typing import TypeVar

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, ValidationError

from .config import settings

T = TypeVar("T", bound=BaseModel)

_NODE_TO_MODEL = {
    "grill": settings.model_grill,
    "extrator": settings.model_extrator,
    "critico": settings.model_critico,
    "consolidador": settings.model_consolidador,
    "refinador": settings.model_refinador,
    "analista": settings.model_analista,
    "arquiteto": settings.model_arquiteto,
    "designer": settings.model_designer,
    "fatiador": settings.model_fatiador,
}


def get_model_name(node: str) -> str:
    """Resolve o nome do modelo para um nó do grafo, a partir da env."""
    if node not in _NODE_TO_MODEL:
        raise ValueError(f"nó desconhecido para roteamento de modelo: {node!r}")
    return _NODE_TO_MODEL[node]


def chat(node: str, **kwargs) -> ChatOpenAI:
    """Cliente de chat para um nó, apontando para o provider configurado."""
    return ChatOpenAI(
        model=get_model_name(node),
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        **kwargs,
    )


# ─── Observabilidade (Langfuse) ───────────────────────────────────────────
@lru_cache(maxsize=1)
def _langfuse_handler():
    """CallbackHandler do Langfuse, ou None se as chaves não estão configuradas.

    No-op quando LANGFUSE_* está vazio: o pipeline roda sem observabilidade.
    Constrói o cliente global explicitamente — nossas envs vêm do pydantic
    (arquivo .env), não do os.environ, então o auto-config do Langfuse não as
    enxergaria. Import preguiçoso: langfuse só é tocado quando ligado.
    """
    if not (settings.langfuse_public_key and settings.langfuse_secret_key):
        return None
    from langfuse import Langfuse
    from langfuse.langchain import CallbackHandler

    Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_host,
    )
    return CallbackHandler()


def _run_config(node: str, session_id: str | None) -> dict:
    """Config do LangChain com o callback do Langfuse (vazio se desligado).

    Agrupa todas as chamadas de um run sob o mesmo `session_id` (= run_id) e
    marca o nó como tag/nome de trace. Vazio quando o Langfuse está desligado,
    caso em que `invoke(config={})` é idêntico a não passar nada.
    """
    handler = _langfuse_handler()
    if handler is None:
        return {}
    metadata: dict = {"langfuse_tags": [node], "langfuse_trace_name": f"grill:{node}"}
    if session_id:
        metadata["langfuse_session_id"] = session_id
    return {"callbacks": [handler], "metadata": metadata}


def structured_call(
    node: str,
    system: str,
    user: str,
    schema: type[T],
    max_retries: int = 2,
    session_id: str | None = None,
) -> T:
    """Chamada tipada com as 3 camadas de blindagem (PRD §3.1).

    A DeepSeek não suporta JSON Schema estrito (`response_format` json_schema),
    e forced tool call conflita com o thinking mode dos modelos `pro`. Então
    usamos a via robusta e uniforme:
      1. `response_format=json_object` + o JSON Schema injetado no prompt
      2. validação Pydantic (`model_validate`)
      3. em falha, re-prompt com o JSON inválido + o erro (máx. `max_retries`)

    Retorna uma instância validada de `schema`; esgotadas as tentativas,
    propaga o último erro.
    """
    model_name = get_model_name(node)
    llm = chat(node).bind(response_format={"type": "json_object"})
    schema_json = json.dumps(schema.model_json_schema(), ensure_ascii=False, indent=2)
    system_full = (
        f"{system}\n\n"
        "Responda APENAS com um objeto JSON válido que siga EXATAMENTE este "
        "JSON Schema (nenhum texto fora do JSON):\n"
        f"{schema_json}"
    )
    messages: list = [SystemMessage(content=system_full), HumanMessage(content=user)]
    last_error: Exception | None = None
    cfg = _run_config(node, session_id)

    # Métricas (Fase 7): tokens acumulam entre re-prompts; latência cobre a
    # chamada inteira. Gravadas no `finally`, valendo para sucesso e falha.
    tokens_in = tokens_out = 0
    t0 = time.perf_counter()
    try:
        for _ in range(max_retries + 1):
            msg = llm.invoke(messages, config=cfg)
            usage = getattr(msg, "usage_metadata", None) or {}
            tokens_in += usage.get("input_tokens", 0) or 0
            tokens_out += usage.get("output_tokens", 0) or 0
            raw = str(msg.content)
            try:
                return schema.model_validate(json.loads(raw))
            except (json.JSONDecodeError, ValidationError) as e:
                last_error = e
                messages.append(AIMessage(content=raw))
                messages.append(
                    HumanMessage(
                        content=(
                            f"O JSON acima falhou na validação: {e}. Responda "
                            "novamente, APENAS com JSON válido que siga o schema."
                        )
                    )
                )

        assert last_error is not None
        raise last_error
    finally:
        _record_metric(node, session_id, model_name, tokens_in, tokens_out, t0)


def _record_metric(
    node: str,
    session_id: str | None,
    model_name: str,
    tokens_in: int,
    tokens_out: int,
    t0: float,
) -> None:
    """Registra a métrica da chamada. Best-effort e isolado (import tardio para
    não puxar o stack de DB em quem só usa o factory de modelos)."""
    try:
        from .metrics import record_llm_call

        record_llm_call(
            node=node,
            session_id=session_id,
            model=model_name,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=int((time.perf_counter() - t0) * 1000),
        )
    except Exception:  # noqa: BLE001 — observabilidade nunca derruba o pipeline.
        pass
