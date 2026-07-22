"""Agente E6: fatiador vertical.

Agrupa as histórias aprovadas em fatias que atravessam UI + API + persistência
+ testes (PRD §4/E6). A regra invariável — nada de fatia de camada única — é
verificada por um validador PURO. O pacote `docs/fatias/F-XXX.md` é MONTADO
pelo sistema (não pelo LLM): os cenários de teste vêm do banco (E5) e o
Definition of Done é fixo, garantindo fidelidade.
"""

from __future__ import annotations

from ..instructions import load_instructions
from ..llm import structured_call
from .grill import _corpus_context
from .schemas import Fatia, MapaFatias

# Definition of Done fixo do template (instructions/fatiador.md).
_DOD = [
    "UI consome a API real (sem mock) e trata erro/loading",
    "API persiste e lê do banco via migration versionada",
    "Todos os cenários desta fatia implementados e passando",
    "Lint + CI verdes; trace da feature visível na observabilidade",
    "Demonstrável: roteiro de demo em 5 passos incluído abaixo",
]


def fatiar(
    project_id: int,
    dossie: str,
    historias: list[dict],
    session_id: str | None = None,
    feedback: str = "",
) -> MapaFatias:
    """Agrupa histórias aprovadas em fatias verticais (walking skeleton 1º).

    `historias`: [{id, title, gherkin, rn_codes}].
    """
    system = load_instructions("fatiador")
    hist = "\n".join(
        f"[id={h['id']}] {h['title']} | RNs: {', '.join(h.get('rn_codes', []))}"
        for h in historias
    )
    partes = [
        "Dossiê do Sistema (DADOS):\n"
        f"<material>\n{dossie}\n</material>\n\n"
        f"Trechos do corpus (DADOS):\n{_corpus_context(project_id)}\n\n"
        "Histórias aprovadas a fatiar (use estes ids em historia_ids):\n"
        f"{hist}\n\n"
        "Agrupe em fatias verticais (MapaFatias). A Fatia 1 é o walking "
        "skeleton (fio de ponta a ponta). Toda fatia cobre API, persistência e UI.",
    ]
    if feedback:
        partes.append(f"\nA tentativa anterior foi rejeitada. Corrija:\n{feedback}")
    return structured_call(
        "fatiador", system, "\n".join(partes), MapaFatias, session_id=session_id
    )


# ─── Validação pura (regra invariável: nunca fatia de camada única) ────────
def fatia_cobre_camadas(fatia: Fatia) -> bool:
    """True se a fatia referencia as três camadas e ≥1 história."""
    return bool(
        fatia.historia_ids
        and fatia.contrato_api.strip()
        and fatia.modelo_dados.strip()
        and fatia.ui.strip()
    )


def validar_fatias(mapa: MapaFatias, ids_validos: set[int]) -> str:
    """Feedback acionável, ou '' se todas as fatias fecham.

    Rejeita: fatia sem alguma das 3 camadas, fatia sem história, e história
    aprovada que nenhuma fatia cobre (nenhuma órfã).
    """
    problemas = []
    if not mapa.fatias:
        return "nenhuma fatia gerada"
    cobertas: set[int] = set()
    for i, f in enumerate(mapa.fatias, start=1):
        if not fatia_cobre_camadas(f):
            problemas.append(
                f"fatia {i} ('{f.nome}') não cobre as 3 camadas (API+dados+UI) "
                "ou não tem história"
            )
        invalidos = set(f.historia_ids) - ids_validos
        if invalidos:
            problemas.append(f"fatia {i} cita histórias inexistentes: {sorted(invalidos)}")
        cobertas |= set(f.historia_ids) & ids_validos
    orfas = ids_validos - cobertas
    if orfas:
        problemas.append(f"histórias aprovadas sem fatia: {sorted(orfas)}")
    return " | ".join(problemas)


# ─── Render do pacote docs/fatias/F-XXX.md ─────────────────────────────────
def renderizar_pacote(
    code: str,
    fatia: dict,
    historias_map: dict[int, dict],
    cenarios_map: dict[int, list[dict]],
) -> str:
    """Monta o markdown do pacote no template do fatiador.md.

    `historias_map`: {id: {title, gherkin, rn_codes}}.
    `cenarios_map`: {id: [{kind, gherkin}]} (do designer de testes, E5).
    """
    ids = fatia.get("historia_ids", [])
    linhas = [f"# {code} — {fatia.get('nome', '')}", "", "## Histórias incluídas"]
    for hid in ids:
        h = historias_map.get(hid)
        if not h:
            continue
        linhas.append(f"### [id={hid}] {h['title']}")
        if h.get("rn_codes"):
            linhas.append(f"RNs: {', '.join(h['rn_codes'])}")
        if h.get("gherkin"):
            linhas.append(f"```gherkin\n{h['gherkin']}\n```")

    linhas += ["", "## Contrato de API proposto", fatia.get("contrato_api", "")]
    linhas += ["", "## Modelo de dados", fatia.get("modelo_dados", "")]
    linhas += ["", "## UI", fatia.get("ui", "")]

    linhas += ["", "## Cenários de teste (do designer de testes)"]
    algum = False
    for hid in ids:
        for c in cenarios_map.get(hid, []):
            algum = True
            linhas.append(f"- [{c.get('kind', '')}] {c.get('gherkin', '')}")
    if not algum:
        linhas.append("_(rode a E5/designer de testes para popular os cenários)_")

    linhas += ["", "## Definition of Done"]
    linhas += [f"- [ ] {item}" for item in _DOD]

    linhas += ["", "## Roteiro de demo"]
    passos = fatia.get("roteiro_demo", [])
    linhas += [f"{i}. {p}" for i, p in enumerate(passos, start=1)] or ["_(a definir)_"]

    return "\n".join(linhas) + "\n"
