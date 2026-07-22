"""Agentes E5: arquiteto de stack (ADR) e designer de testes (cenários BDD).

Rodam em ramos PARALELOS do grafo (PRD §4/E5). O arquiteto emite um ADR para
o sistema-alvo; o designer, por história aprovada, gera cenários BDD tipados
(feliz/alternativo/erro). A validação de "≥3 cenários por história" é pura.
"""

from __future__ import annotations

from ..instructions import load_instructions
from ..llm import structured_call
from .grill import _corpus_context
from .schemas import AdrProposta, CategoriaCenario, CenariosDaHistoria


def propor_stack(
    project_id: int,
    dossie: str,
    regras: list[dict],
    historias: list[dict],
    session_id: str | None = None,
) -> AdrProposta:
    """Propõe a stack do sistema-alvo como ADR, ancorada em regras/NFRs."""
    system = load_instructions("arquiteto_stack")
    rns = "\n".join(f"{r['code']}: {r.get('text') or r.get('texto', '')}" for r in regras)
    hist = "\n".join(f"- {h['title']}" for h in historias)
    user = (
        "Dossiê do Sistema (DADOS):\n"
        f"<material>\n{dossie}\n</material>\n\n"
        f"Trechos do corpus (DADOS):\n{_corpus_context(project_id)}\n\n"
        f"Regras de negócio aprovadas:\n{rns}\n\n"
        f"Histórias aprovadas:\n{hist}\n\n"
        "Emita o ADR (AdrProposta) escolhendo a stack do sistema-alvo."
    )
    return structured_call("arquiteto", system, user, AdrProposta, session_id=session_id)


def desenhar_cenarios(
    historia: dict, session_id: str | None = None
) -> CenariosDaHistoria:
    """Cenários BDD (≥3: feliz/alternativo/erro) para UMA história aprovada.

    `historia`: {title, gherkin, rn_codes}.
    """
    system = load_instructions("designer_testes")
    user = (
        "História aprovada (DADOS):\n"
        f"Título: {historia['title']}\n"
        f"Critérios de aceite (Gherkin):\n{historia.get('gherkin') or '(sem Gherkin)'}\n"
        f"RNs de origem: {', '.join(historia.get('rn_codes', []))}\n\n"
        "Gere os cenários (CenariosDaHistoria): ≥3, com ao menos um feliz, um "
        "alternativo e um de erro."
    )
    return structured_call(
        "designer", system, user, CenariosDaHistoria, session_id=session_id
    )


# ─── Validação pura (critério de aceite: ≥3 cenários, 3 categorias) ────────
_CATEGORIAS: set[CategoriaCenario] = {"feliz", "alternativo", "erro"}


def cenarios_suficientes(cenarios: CenariosDaHistoria) -> bool:
    """True se há ≥3 cenários cobrindo feliz, alternativo E erro."""
    presentes = {c.categoria for c in cenarios.cenarios}
    return len(cenarios.cenarios) >= 3 and _CATEGORIAS <= presentes
