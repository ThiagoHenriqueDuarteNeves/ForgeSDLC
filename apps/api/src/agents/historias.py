"""Agente E4: analista de histórias (RNs aprovadas → épicos + histórias INVEST).

O gerador é uma chamada de LLM tipada; a validação da matriz de rastreio
(RN↔US) é PURA em Python — é ela que garante os critérios de aceite da fase:
nenhuma RN aprovada órfã e nenhuma história sem RN de origem. O grafo usa
essas funções no loop de auto-refinamento (máx. 3 iterações).
"""

from __future__ import annotations

from ..instructions import load_instructions
from ..llm import structured_call
from .grill import _corpus_context
from .schemas import MapaHistorias


def gerar_historias(
    project_id: int,
    dossie: str,
    regras_aprovadas: list[dict],
    session_id: str | None = None,
    feedback: str = "",
) -> MapaHistorias:
    """Gera épicos + histórias cobrindo as RNs aprovadas.

    `regras_aprovadas`: lista de {code, texto, tipo, fonte}. `feedback` carrega
    o resultado da validação anterior (RNs órfãs / histórias sem RN) para o
    loop de auto-refinamento.
    """
    system = load_instructions("analista_requisitos")
    rns = "\n".join(f"{r['code']}: {r['texto']}" for r in regras_aprovadas)
    partes = [
        "Dossiê do Sistema (DADOS):\n"
        f"<material>\n{dossie}\n</material>\n\n"
        f"Trechos do corpus (DADOS):\n{_corpus_context(project_id)}\n\n"
        "Regras de negócio APROVADAS a cobrir (toda RN precisa aparecer em ≥1 "
        f"história):\n{rns}",
    ]
    if feedback:
        partes.append(
            "\nA tentativa anterior falhou na validação da matriz. Corrija "
            f"exatamente isto:\n{feedback}"
        )
    return structured_call(
        "analista", system, "\n".join(partes), MapaHistorias, session_id=session_id
    )


# ─── Validação da matriz de rastreabilidade (pura, determinística) ─────────
def rns_orfas(mapa: MapaHistorias, codigos_aprovados: set[str]) -> set[str]:
    """RNs aprovadas que nenhuma história cobre (têm de ser zero)."""
    cobertas = {c for h in mapa.historias for c in h.rns_cobertas}
    return codigos_aprovados - cobertas


def historias_sem_rn(mapa: MapaHistorias) -> list[str]:
    """Histórias sem RN de origem e não marcadas como derivadas-de-jornada."""
    return [
        h.id
        for h in mapa.historias
        if not h.rns_cobertas and not h.derivada_de_jornada
    ]


def rns_inexistentes(mapa: MapaHistorias, codigos_aprovados: set[str]) -> set[str]:
    """Códigos citados pelas histórias que não existem no conjunto aprovado."""
    citadas = {c for h in mapa.historias for c in h.rns_cobertas}
    return citadas - codigos_aprovados


def validar_matriz(mapa: MapaHistorias, codigos_aprovados: set[str]) -> str:
    """Retorna feedback acionável, ou '' se a matriz fecha.

    Fecha quando: nenhuma RN órfã, nenhuma história sem RN de origem, nenhum
    código citado inexistente.
    """
    problemas = []
    orfas = rns_orfas(mapa, codigos_aprovados)
    if orfas:
        problemas.append(f"RNs aprovadas sem história: {', '.join(sorted(orfas))}")
    sem_rn = historias_sem_rn(mapa)
    if sem_rn:
        problemas.append(
            f"histórias sem RN de origem (nem derivadas-de-jornada): {', '.join(sem_rn)}"
        )
    inexistentes = rns_inexistentes(mapa, codigos_aprovados)
    if inexistentes:
        problemas.append(
            f"histórias citam RNs inexistentes: {', '.join(sorted(inexistentes))}"
        )
    return " | ".join(problemas)
