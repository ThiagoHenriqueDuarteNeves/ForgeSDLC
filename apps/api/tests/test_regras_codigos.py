"""Numeração determinística das RNs (Python, não LLM)."""

from src.agents.regras import _completar_codigos, _numerar
from src.agents.schemas import ConjuntoRegras, RegraConsolidada


def _regra(code: str = "", texto: str = "x") -> RegraConsolidada:
    return RegraConsolidada(
        code=code, texto=texto, tipo="validacao", fonte="Q-01", confianca="alta"
    )


def test_numerar_sequencial_a_partir_de_1():
    conj = ConjuntoRegras(regras=[_regra(), _regra(), _regra()])
    _numerar(conj)
    assert [r.code for r in conj.regras] == ["RN-001", "RN-002", "RN-003"]


def test_completar_preserva_existentes_e_da_codigo_aos_novos():
    # duas já numeradas + uma dividida (code vazio) → recebe o próximo livre.
    conj = ConjuntoRegras(
        regras=[_regra("RN-001"), _regra("RN-002"), _regra("")],
    )
    _completar_codigos(conj)
    assert [r.code for r in conj.regras] == ["RN-001", "RN-002", "RN-003"]


def test_completar_nao_relabela_apos_gap():
    # se o refinador removeu a RN-002, os códigos restantes NÃO deslizam.
    conj = ConjuntoRegras(regras=[_regra("RN-001"), _regra("RN-003"), _regra("")])
    _completar_codigos(conj)
    assert [r.code for r in conj.regras] == ["RN-001", "RN-003", "RN-004"]
