"""Agentes do subgrafo E3: extração e refino de regras de negócio.

Fluxo (PRD §4/E3): extrator ×3 em paralelo (self-consistency) → consolidador
(dedup + confiança por consenso) → crítico (rubrica fixa, agente separado) ⇄
refinador (reescreve só as reprovadas), máx. 3 iterações.

Cada função é pura (recebe dados, chama o LLM via blindagem de src/llm.py) e
recebe `session_id` para agrupar o trace no Langfuse pelo run. A numeração
`RN-XXX` é atribuída em Python (determinística, casável com a unique
constraint do banco), nunca pelo LLM.
"""

from __future__ import annotations

from ..instructions import load_instructions
from ..llm import structured_call
from .grill import _corpus_context
from .schemas import (
    ConjuntoRegras,
    ExtracaoRegras,
    RegraExtraida,
    RelatorioCritico,
    RodadaPerguntas,
)


def _dados(project_id: int, dossie: str) -> str:
    """Bloco de DADOS (dossiê + corpus) delimitado — nunca instruções."""
    return (
        "Dossiê do Sistema (DADOS):\n"
        f"<material>\n{dossie}\n</material>\n\n"
        "Trechos do corpus (DADOS):\n"
        f"{_corpus_context(project_id)}"
    )


def extrair_regras(
    project_id: int, dossie: str, session_id: str | None = None
) -> ExtracaoRegras:
    """UMA extração de regras (o subgrafo a executa 3× em paralelo)."""
    system = load_instructions("extrator_regras")
    user = (
        f"{_dados(project_id, dossie)}\n\n"
        "Extraia todas as regras de negócio sustentadas por este material, "
        "cada uma atômica, testável e com fonte."
    )
    return structured_call("extrator", system, user, ExtracaoRegras, session_id=session_id)


def _numerar(conjunto: ConjuntoRegras) -> ConjuntoRegras:
    """Atribui RN-001, RN-002… na ordem (primeira numeração, na consolidação)."""
    for i, regra in enumerate(conjunto.regras, start=1):
        regra.code = f"RN-{i:03d}"
    return conjunto


def _completar_codigos(conjunto: ConjuntoRegras) -> ConjuntoRegras:
    """Preserva códigos existentes; dá códigos novos só às regras sem code.

    Usado após o refino: o crítico referencia RNs pelo código, então relabelar
    tudo quebraria a rastreabilidade. Regras que o refinador dividiu chegam com
    `code` vazio e recebem o próximo número livre.
    """
    usados = {
        int(r.code.split("-")[1])
        for r in conjunto.regras
        if r.code and r.code.startswith("RN-") and r.code.split("-")[1].isdigit()
    }
    proximo = max(usados, default=0) + 1
    for regra in conjunto.regras:
        if not regra.code:
            regra.code = f"RN-{proximo:03d}"
            proximo += 1
    return conjunto


def consolidar(
    extracoes: list[ExtracaoRegras], session_id: str | None = None
) -> ConjuntoRegras:
    """Funde as 3 extrações num conjunto único e numera as regras."""
    system = load_instructions("consolidador_regras")
    blocos = []
    for i, ext in enumerate(extracoes, start=1):
        linhas = [f"— Extração {i} —"]
        for r in ext.regras:
            linhas.append(f"[{r.tipo}] {r.texto} (fonte: {r.fonte})")
        blocos.append("\n".join(linhas))
    user = (
        "As 3 extrações independentes do mesmo material estão abaixo. Funda "
        "variantes da mesma regra e atribua confiança por consenso (alta=nas 3, "
        "media=em 2, baixa=em 1). Deixe `code` vazio.\n\n" + "\n\n".join(blocos)
    )
    conjunto = structured_call(
        "consolidador", system, user, ConjuntoRegras, session_id=session_id
    )
    return _numerar(conjunto)


def _formatar_conjunto(conjunto: ConjuntoRegras) -> str:
    linhas = []
    for r in conjunto.regras:
        linhas.append(
            f"{r.code} [{r.tipo}, confiança {r.confianca}] {r.texto} "
            f"(fonte: {r.fonte})"
        )
    return "\n".join(linhas)


def criticar(
    conjunto: ConjuntoRegras, session_id: str | None = None
) -> RelatorioCritico:
    """Avalia cada RN pela rubrica fixa (agente separado do extrator)."""
    system = load_instructions("critico_regras")
    user = (
        "Avalie cada regra abaixo pela rubrica. Aprovada só se os 5 critérios "
        "forem verdadeiros. Referencie cada avaliação pelo `code`.\n\n"
        f"{_formatar_conjunto(conjunto)}"
    )
    return structured_call("critico", system, user, RelatorioCritico, session_id=session_id)


def refinar(
    conjunto: ConjuntoRegras,
    relatorio: RelatorioCritico,
    session_id: str | None = None,
) -> ConjuntoRegras:
    """Reescreve só as RNs reprovadas; mantém as aprovadas e os códigos."""
    system = load_instructions("refinador_regras")
    problemas = []
    for av in relatorio.avaliacoes:
        if not av.aprovada:
            problemas.append(f"{av.code}: {'; '.join(av.problemas) or 'reprovada'}")
    user = (
        "Conjunto atual:\n"
        f"{_formatar_conjunto(conjunto)}\n\n"
        "Regras reprovadas pelo crítico (conserte APENAS estas, preservando os "
        "códigos; copie as aprovadas inalteradas):\n" + "\n".join(problemas)
    )
    conjunto = structured_call(
        "refinador", system, user, ConjuntoRegras, session_id=session_id
    )
    return _completar_codigos(conjunto)


# ─── Contestação dirigida (PRD §4/E3.1) ───────────────────────────────────
def perguntar_contestacao(
    project_id: int, rn_texto: str, motivo: str, session_id: str | None = None
) -> RodadaPerguntas:
    """Rodada dirigida do Grill Me sobre a lacuna de uma RN contestada."""
    system = load_instructions("contestacao")
    user = (
        f"{_dados(project_id, '(dossiê já consolidado)')}\n\n"
        f"Regra CONTESTADA (errada): {rn_texto}\n"
        f"Motivo da contestação: {motivo}\n\n"
        "Momento 1 — faça até 3 perguntas fechadas focadas SÓ nessa lacuna."
    )
    return structured_call("grill", system, user, RodadaPerguntas, session_id=session_id)


def resolver_contestacao(
    project_id: int,
    rn_texto: str,
    motivo: str,
    respostas: dict[str, str],
    session_id: str | None = None,
) -> RegraExtraida:
    """Sintetiza a RN corrigida a partir das respostas do PO (supersede)."""
    system = load_instructions("contestacao")
    respostas_txt = "\n".join(f"{qid}: {resp}" for qid, resp in respostas.items())
    user = (
        f"{_dados(project_id, '(dossiê já consolidado)')}\n\n"
        f"Regra CONTESTADA (errada): {rn_texto}\n"
        f"Motivo da contestação: {motivo}\n\n"
        f"Respostas do PO na rodada dirigida:\n{respostas_txt}\n\n"
        "Momento 2 — produza UMA regra corrigida (RegraExtraida) que substitui "
        "a errada, com fonte apontando para a resposta (contestação Q-XX)."
    )
    return structured_call("extrator", system, user, RegraExtraida, session_id=session_id)
