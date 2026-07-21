"""Factory único de clientes de LLM.

REGRA (CLAUDE.md): nenhum outro módulo constrói cliente de LLM nem importa
SDK de provider direto. Tudo passa por aqui, parametrizado por env, para que
trocar de provider (DeepSeek → OpenAI → vLLM local) seja mudança de .env.

Implementação real chega na Fase 3, junto com o primeiro nó do grafo. Aqui
fica apenas o contrato, para fixar o ponto de acoplamento desde a fundação.
"""

from .config import settings


def get_model_name(node: str) -> str:
    """Resolve o nome do modelo para um nó do grafo, a partir da env.

    Ex.: get_model_name("grill") -> settings.model_grill.
    """
    mapping = {
        "grill": settings.model_grill,
        "extrator": settings.model_extrator,
        "critico": settings.model_critico,
        "consolidador": settings.model_consolidador,
    }
    if node not in mapping:
        raise ValueError(f"nó desconhecido para roteamento de modelo: {node!r}")
    return mapping[node]
