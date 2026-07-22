"""Harness de avaliação offline do pipeline — Fase 7 / PRD §7.

Roda os agentes de raciocínio (E3 extração/refino de RNs + E4 histórias) contra
um dataset de 3 projetos-exemplo fictícios e pontua a qualidade com DeepEval
(um juiz LLM). É o que `scripts/eval.py` orquestra e o job noturno do CI dispara.

Dependências pesadas (deepeval, agentes/LLM) são importadas SÓ dentro das
funções de execução — assim este módulo importa limpo no runtime da API (que
não instala o grupo `eval`) e nos testes determinísticos, que exercitam apenas
o dataset e a agregação, sem tocar em LLM.

O dataset vive aqui como constante (fonte de verdade) e é empurrado para o
Langfuse como dataset versionado por `push_langfuse_dataset`.
"""

from __future__ import annotations

from statistics import mean

from .observability import get_logger

log = get_logger("eval")

# ─── Dataset: 3 projetos-exemplo fictícios ─────────────────────────────────
# `descricao` faz o papel de dossiê (a avaliação pula o Grill Me, que é HITL).
# `regras_esperadas` é referência humana para leitura do relatório (o juiz LLM
# pontua a saída real dos agentes, não faz match textual com estas).
DATASET: list[dict] = [
    {
        "nome": "Biblioteca comunitária",
        "descricao": (
            "Sistema de empréstimo de uma biblioteca de bairro. Um associado "
            "pode ter no máximo 3 livros emprestados ao mesmo tempo. O prazo de "
            "devolução é de 15 dias corridos; após esse prazo incide multa de "
            "R$ 1,00 por dia de atraso por livro. Um associado com multa em "
            "aberto não pode fazer novos empréstimos. Livros marcados como "
            "'referência' não podem ser emprestados, apenas consultados no local."
        ),
        "regras_esperadas": [
            "Máximo de 3 empréstimos simultâneos por associado.",
            "Prazo de devolução de 15 dias corridos.",
            "Multa de R$ 1,00 por dia de atraso por livro.",
            "Associado com multa em aberto fica bloqueado para novos empréstimos.",
            "Livros de referência não são emprestáveis.",
        ],
    },
    {
        "nome": "Estacionamento rotativo",
        "descricao": (
            "Aplicativo de estacionamento rotativo urbano. A primeira hora custa "
            "R$ 5,00 e cada hora adicional custa R$ 3,00, cobradas por hora "
            "iniciada. O tempo máximo permitido em uma mesma vaga é de 2 horas em "
            "zona azul. Motos pagam metade da tarifa. Idosos e pessoas com "
            "deficiência têm direito a vagas reservadas e isenção de tarifa "
            "mediante cadastro válido."
        ),
        "regras_esperadas": [
            "Primeira hora R$ 5,00; hora adicional R$ 3,00, por hora iniciada.",
            "Permanência máxima de 2 horas em zona azul.",
            "Motos pagam 50% da tarifa.",
            "Idosos e PcD com cadastro válido têm isenção e vaga reservada.",
        ],
    },
    {
        "nome": "Loja online de assinaturas",
        "descricao": (
            "E-commerce de assinaturas mensais de café. O cliente escolhe um "
            "plano (básico, premium) com renovação automática mensal. O "
            "cancelamento pode ser feito a qualquer momento e vale até o fim do "
            "ciclo já pago (sem reembolso proporcional). A partir da terceira "
            "renovação consecutiva, o cliente ganha 10% de desconto fidelidade. "
            "Pagamentos recusados suspendem a assinatura após 3 tentativas em "
            "dias alternados."
        ),
        "regras_esperadas": [
            "Renovação automática mensal do plano escolhido.",
            "Cancelamento vale até o fim do ciclo pago, sem reembolso proporcional.",
            "10% de desconto fidelidade a partir da 3ª renovação consecutiva.",
            "Assinatura suspensa após 3 tentativas de pagamento recusadas.",
        ],
    },
]

_REQUIRED = {"nome", "descricao", "regras_esperadas"}


def dataset_items() -> list[dict]:
    """Retorna o dataset validado (levanta se algum item estiver malformado)."""
    for i, item in enumerate(DATASET):
        faltando = _REQUIRED - item.keys()
        if faltando:
            raise ValueError(f"item {i} do dataset sem campos: {sorted(faltando)}")
        if not item["regras_esperadas"]:
            raise ValueError(f"item {i} ('{item['nome']}') sem regras esperadas")
    return DATASET


# ─── Langfuse: dataset versionado ──────────────────────────────────────────
def push_langfuse_dataset(name: str = "forge-eval") -> int:
    """Cria/atualiza o dataset no Langfuse. 0 se as chaves não estão setadas."""
    from .config import settings

    if not (settings.langfuse_public_key and settings.langfuse_secret_key):
        log.info("langfuse não configurado; pulando push do dataset")
        return 0

    from langfuse import Langfuse

    client = Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_host,
    )
    client.create_dataset(name=name, description="Forge SDLC — 3 projetos-exemplo (Fase 7)")
    for item in dataset_items():
        client.create_dataset_item(
            dataset_name=name,
            input={"nome": item["nome"], "descricao": item["descricao"]},
            expected_output={"regras_esperadas": item["regras_esperadas"]},
        )
    log.info("dataset empurrado para o langfuse", name=name, itens=len(DATASET))
    return len(DATASET)


# ─── Juiz LLM (DeepEval sobre o provider configurado) ──────────────────────
def _judge():
    """Modelo-juiz do DeepEval sobre o mesmo provider (via factory src/llm.py)."""
    from deepeval.models.base_model import DeepEvalBaseLLM
    from langchain_core.messages import HumanMessage

    from .llm import chat

    class ProviderJudge(DeepEvalBaseLLM):
        def __init__(self) -> None:
            self._llm = chat("critico")

        def load_model(self):
            return self._llm

        def generate(self, prompt: str) -> str:
            return str(self._llm.invoke([HumanMessage(content=prompt)]).content)

        async def a_generate(self, prompt: str) -> str:
            return self.generate(prompt)

        def get_model_name(self) -> str:
            return "provider-judge"

    return ProviderJudge()


def _metricas(judge, threshold: float):
    from deepeval.metrics import GEval
    from deepeval.test_case import LLMTestCaseParams

    rn = GEval(
        name="Qualidade da RN",
        criteria=(
            "A saída é UMA regra de negócio atômica e testável (verificável "
            "objetivamente), não um requisito de UI disfarçado nem várias regras "
            "juntas. Penalize regras vagas ou não verificáveis."
        ),
        evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT],
        model=judge,
        threshold=threshold,
        async_mode=False,
    )
    hist = GEval(
        name="Qualidade da história",
        criteria=(
            "A saída é uma história de usuário no formato INVEST, com ator, ação "
            "e valor claros e critérios de aceite em Gherkin coerentes. Penalize "
            "histórias sem valor de negócio ou sem critérios verificáveis."
        ),
        evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT],
        model=judge,
        threshold=threshold,
        async_mode=False,
    )
    return rn, hist


def _gerar_artefatos(item: dict) -> tuple[list[dict], list[dict]]:
    """Roda E3 (extrair×3 → consolidar → criticar → refinar) e E4 sobre a
    descrição do projeto, com corpus vazio (a descrição faz de dossiê)."""
    import src.agents.historias as H
    import src.agents.regras as R

    orig_r, orig_h = R._corpus_context, H._corpus_context
    R._corpus_context = lambda _pid: ""  # type: ignore[assignment]
    H._corpus_context = lambda _pid: ""  # type: ignore[assignment]
    try:
        dossie = item["descricao"]
        extracoes = [R.extrair_regras(0, dossie) for _ in range(3)]
        conjunto = R.consolidar(extracoes)
        relatorio = R.criticar(conjunto)
        conjunto = R.refinar(conjunto, relatorio)
        rns = [
            {"code": r.code, "texto": r.texto, "tipo": r.tipo, "fonte": r.fonte}
            for r in conjunto.regras
        ]
        mapa = H.gerar_historias(0, dossie, rns)
        historias = [
            {"id": h.id, "texto": f"{h.ator} quer {h.acao} para {h.valor}",
             "gherkin": "\n".join(h.criterios_gherkin)}
            for h in mapa.historias
        ]
    finally:
        R._corpus_context, H._corpus_context = orig_r, orig_h  # type: ignore[assignment]
    return rns, historias


def avaliar_projeto(item: dict, judge=None, threshold: float = 0.6) -> dict:
    """Gera RNs+histórias do item e pontua a qualidade média com o juiz LLM."""
    from deepeval.test_case import LLMTestCase

    judge = judge or _judge()
    m_rn, m_hist = _metricas(judge, threshold)
    rns, historias = _gerar_artefatos(item)
    contexto = item["descricao"][:600]

    def _pontuar(metric, textos: list[str]) -> float | None:
        notas: list[float] = []
        for t in textos:
            metric.measure(LLMTestCase(input=contexto, actual_output=t))
            if metric.score is not None:
                notas.append(metric.score)
        return mean(notas) if notas else None

    resultado = {
        "nome": item["nome"],
        "n_regras": len(rns),
        "n_historias": len(historias),
        "score_rn": _pontuar(m_rn, [r["texto"] for r in rns]),
        "score_hist": _pontuar(m_hist, [h["texto"] for h in historias]),
    }
    log.info("projeto avaliado", **resultado)
    return resultado


# ─── Agregação (pura, determinística) ──────────────────────────────────────
def agregar_scores(resultados: list[dict], threshold: float = 0.6) -> dict:
    """Média dos scores por métrica + veredito contra o threshold."""
    rn = [r["score_rn"] for r in resultados if r.get("score_rn") is not None]
    hist = [r["score_hist"] for r in resultados if r.get("score_hist") is not None]
    media_rn = mean(rn) if rn else 0.0
    media_hist = mean(hist) if hist else 0.0
    return {
        "projetos": len(resultados),
        "media_score_rn": media_rn,
        "media_score_hist": media_hist,
        "threshold": threshold,
        "aprovado": bool(rn and hist and media_rn >= threshold and media_hist >= threshold),
    }
