"""Schemas tipados das saídas dos agentes (Pydantic).

Contratos que os nós do grafo emitem — validados pela blindagem de 3 camadas
(src/llm.py). Ver instructions/*.md para o significado dos campos.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

TipoRegra = Literal[
    "invariante", "validacao", "calculo", "politica", "processo", "permissao"
]
Confianca = Literal["alta", "media", "baixa"]


class Pergunta(BaseModel):
    id: str = Field(description="identificador curto, ex.: Q-01")
    texto: str = Field(description="a pergunta, fechada quando possível")
    motivo: str = Field(description="por que ela importa (lacuna que fecha)")
    item_checklist: str = Field(description="item do checklist que ela cobre")


class RodadaPerguntas(BaseModel):
    """Saída do nó grill_me a cada rodada."""

    cobertura: dict[str, str] = Field(
        description="item do checklist -> 'coberto' | 'parcial' | 'ausente'"
    )
    perguntas: list[Pergunta] = Field(
        default_factory=list, description="até 5 perguntas priorizadas por impacto"
    )
    cobertura_suficiente: bool = Field(
        description=(
            "true quando itens 1-4 estão 'coberto' e os demais ao menos "
            "'parcial' — sinaliza que o dossiê pode ser gerado"
        )
    )


class Dossie(BaseModel):
    """Dossiê do Sistema — saída final do Grill Me, em Markdown."""

    markdown: str = Field(
        description="documento com as 8 seções do checklist, citando fontes"
    )


# ─── E3: extração e refino de regras de negócio ───────────────────────────
class RegraExtraida(BaseModel):
    """Uma regra crua, saída de UMA das 3 extrações paralelas (sem código)."""

    texto: str = Field(description="a regra, afirmativa, atômica e testável")
    tipo: TipoRegra = Field(description="categoria da regra")
    fonte: str = Field(description="material (arquivo,p.X) ou resposta Q-XX; obrigatória")


class ExtracaoRegras(BaseModel):
    """Saída de um nó extrator (self-consistency: roda 3× em paralelo)."""

    regras: list[RegraExtraida] = Field(default_factory=list)


class RegraConsolidada(BaseModel):
    """Regra após fusão/dedup. `code` é atribuído pelo Python, não pelo LLM."""

    code: str = Field(default="", description="RN-XXX — vazio na saída do LLM")
    texto: str
    tipo: TipoRegra
    fonte: str
    confianca: Confianca = Field(
        description="alta=nas 3 extrações, media=em 2, baixa=em 1"
    )


class ConjuntoRegras(BaseModel):
    """Conjunto consolidado/refinado — saída do consolidador e do refinador."""

    regras: list[RegraConsolidada] = Field(default_factory=list)


class AvaliacaoRegra(BaseModel):
    """Julgamento do crítico sobre UMA regra, pela rubrica fixa."""

    code: str = Field(description="RN-XXX avaliada")
    fonte_citada: bool
    testavel: bool
    atomica: bool
    e_regra_negocio: bool
    sem_contradicao: bool
    aprovada: bool = Field(description="true só se os 5 critérios são true")
    problemas: list[str] = Field(
        default_factory=list, description="problemas acionáveis; vazio se aprovada"
    )


class RelatorioCritico(BaseModel):
    """Saída do crítico: avaliação por regra + veredito agregado."""

    avaliacoes: list[AvaliacaoRegra] = Field(default_factory=list)
    todas_aprovadas: bool


# ─── E4: épicos e histórias INVEST ────────────────────────────────────────
class Epico(BaseModel):
    id: str = Field(description="identificador curto, ex.: EP-01")
    nome: str
    objetivo: str = Field(description="a capacidade do sistema que o épico entrega")


class Historia(BaseModel):
    id: str = Field(description="identificador curto, ex.: US-01")
    epico_id: str = Field(description="id do épico ao qual pertence")
    ator: str
    acao: str
    valor: str
    criterios_gherkin: list[str] = Field(
        default_factory=list, description="cenários Gherkin (Dado/Quando/Então)"
    )
    rns_cobertas: list[str] = Field(
        default_factory=list, description="códigos RN-XXX que a história implementa"
    )
    derivada_de_jornada: bool = Field(
        default=False,
        description="true só para história sem RN, criada para fechar a jornada",
    )


class MapaHistorias(BaseModel):
    """Saída do analista de histórias (E4): backlog rastreável."""

    epicos: list[Epico] = Field(default_factory=list)
    historias: list[Historia] = Field(default_factory=list)
