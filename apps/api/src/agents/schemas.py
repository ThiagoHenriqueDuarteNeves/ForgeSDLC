"""Schemas tipados das saídas dos agentes (Pydantic).

Contratos que os nós do grafo emitem — validados pela blindagem de 3 camadas
(src/llm.py). Ver instructions/grill_me.md para o significado dos campos.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


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
