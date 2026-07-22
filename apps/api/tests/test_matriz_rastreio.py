"""Critérios de aceite da Fase 4 — validação PURA da matriz RN↔US (sem LLM).

Garante que: nenhuma RN aprovada fica órfã, história sem RN de origem é
rejeitada, e código de RN inexistente é detectado.
"""

from src.agents.historias import (
    historias_sem_rn,
    rns_inexistentes,
    rns_orfas,
    validar_matriz,
)
from src.agents.schemas import Epico, Historia, MapaHistorias


def _historia(hid: str, rns: list[str], derivada: bool = False) -> Historia:
    return Historia(
        id=hid,
        epico_id="EP-01",
        ator="usuário",
        acao="fazer algo",
        valor="obter valor",
        criterios_gherkin=["Dado X\nQuando Y\nEntão Z"],
        rns_cobertas=rns,
        derivada_de_jornada=derivada,
    )


def _mapa(historias: list[Historia]) -> MapaHistorias:
    return MapaHistorias(
        epicos=[Epico(id="EP-01", nome="Épico", objetivo="obj")],
        historias=historias,
    )


def test_matriz_fecha_quando_todas_rns_cobertas():
    mapa = _mapa([_historia("US-01", ["RN-001", "RN-002"])])
    assert validar_matriz(mapa, {"RN-001", "RN-002"}) == ""


def test_rn_orfa_e_detectada():
    mapa = _mapa([_historia("US-01", ["RN-001"])])
    orfas = rns_orfas(mapa, {"RN-001", "RN-002"})
    assert orfas == {"RN-002"}
    assert "RN-002" in validar_matriz(mapa, {"RN-001", "RN-002"})


def test_historia_sem_rn_de_origem_e_rejeitada():
    mapa = _mapa([_historia("US-09", [])])
    assert historias_sem_rn(mapa) == ["US-09"]
    assert "US-09" in validar_matriz(mapa, {"RN-001"})  # + RN-001 vira órfã


def test_derivada_de_jornada_sem_rn_e_permitida():
    mapa = _mapa(
        [
            _historia("US-01", ["RN-001"]),
            _historia("US-02", [], derivada=True),
        ]
    )
    assert historias_sem_rn(mapa) == []  # derivada não conta como sem-RN
    assert validar_matriz(mapa, {"RN-001"}) == ""


def test_rn_inexistente_citada_e_detectada():
    mapa = _mapa([_historia("US-01", ["RN-001", "RN-999"])])
    assert rns_inexistentes(mapa, {"RN-001"}) == {"RN-999"}
    assert "RN-999" in validar_matriz(mapa, {"RN-001"})
