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


# ─── E5: arquiteto de stack (ADR) ─────────────────────────────────────────
class OpcaoStack(BaseModel):
    stack: str = Field(description="a stack considerada (front/back/banco/infra)")
    pros: str
    contras: str


class AdrProposta(BaseModel):
    """ADR do sistema-alvo — saída do arquiteto de stack."""

    contexto: str = Field(description="o que nos NFRs/regras força a decisão")
    opcoes: list[OpcaoStack] = Field(default_factory=list)
    decisao: str = Field(description="a stack escolhida, item a item, e por quê")
    consequencias: list[str] = Field(default_factory=list)


# ─── E5: designer de testes (cenários BDD por história) ────────────────────
CategoriaCenario = Literal["feliz", "alternativo", "erro"]
NivelTeste = Literal["unit", "integracao", "e2e"]


class Cenario(BaseModel):
    nome: str
    categoria: CategoriaCenario = Field(description="feliz | alternativo | erro")
    nivel: NivelTeste = Field(description="onde o dev implementa: unit|integracao|e2e")
    gherkin: str = Field(description="Dado/Quando/Então, testando UMA coisa")
    rns: list[str] = Field(default_factory=list, description="RN-XXX de origem")


class CenariosDaHistoria(BaseModel):
    """Cenários de UMA história (o designer roda por história). Mín. 3."""

    cenarios: list[Cenario] = Field(default_factory=list)


# ─── E6: fatiador vertical ────────────────────────────────────────────────
class Fatia(BaseModel):
    """Uma fatia vertical: atravessa UI + API + persistência + testes."""

    nome: str = Field(description="nome curto da fatia")
    historia_ids: list[int] = Field(
        default_factory=list, description="ids das histórias aprovadas incluídas (≥1)"
    )
    contrato_api: str = Field(description="endpoints/verbos/exemplos — camada API")
    modelo_dados: str = Field(description="tabelas/colunas/migrations — persistência")
    ui: str = Field(description="telas/componentes/estados — camada UI")
    roteiro_demo: list[str] = Field(
        default_factory=list, description="5 passos para demonstrar a fatia"
    )


class MapaFatias(BaseModel):
    """Saída do fatiador (E6): fatias verticais que cobrem as histórias."""

    fatias: list[Fatia] = Field(default_factory=list)
