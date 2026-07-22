"""Critérios de aceite da Fase 6 (E6, fatiador vertical).

- validador puro: regra invariável (nunca fatia de camada única) + sem órfã;
- render do pacote F-XXX.md com as seções e cenários do banco;
- persistência: Slice + package_md + auditoria.
"""

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.agents.fatiador import (
    fatia_cobre_camadas,
    injetar_cenarios,
    renderizar_pacote,
    validar_fatias,
)
from src.agents.schemas import Fatia, MapaFatias
from src.db import engine
from src.models import (
    AuditLog,
    Epic,
    Project,
    Run,
    ScenarioKind,
    Slice,
    Story,
    TestScenario,
)
from src.services_regras import persistir_fatias


@pytest.fixture
def session():
    conn = engine.connect()
    trans = conn.begin()
    s = Session(bind=conn, join_transaction_mode="create_savepoint")
    try:
        yield s
    finally:
        s.close()
        trans.rollback()
        conn.close()


def _fatia(**kw) -> Fatia:
    base = dict(
        nome="Cadastro",
        historia_ids=[1],
        contrato_api="POST /x",
        modelo_dados="tabela x",
        ui="tela x",
        roteiro_demo=["abrir", "cadastrar"],
    )
    base.update(kw)
    return Fatia(**base)


# ─── validador (regra invariável: nunca camada única) ──────────────────────
def test_fatia_com_as_3_camadas_e_valida():
    assert fatia_cobre_camadas(_fatia()) is True


def test_fatia_sem_ui_e_rejeitada():
    assert fatia_cobre_camadas(_fatia(ui="  ")) is False


def test_fatia_sem_historia_e_rejeitada():
    assert fatia_cobre_camadas(_fatia(historia_ids=[])) is False


def test_validar_detecta_historia_orfa():
    mapa = MapaFatias(fatias=[_fatia(historia_ids=[1])])
    fb = validar_fatias(mapa, {1, 2})
    assert "2" in fb  # história 2 sem fatia


def test_validar_detecta_id_inexistente():
    mapa = MapaFatias(fatias=[_fatia(historia_ids=[1, 99])])
    fb = validar_fatias(mapa, {1})
    assert "99" in fb


def test_validar_fecha_quando_tudo_certo():
    mapa = MapaFatias(fatias=[_fatia(historia_ids=[1, 2])])
    assert validar_fatias(mapa, {1, 2}) == ""


# ─── render do pacote ──────────────────────────────────────────────────────
def test_render_pacote_tem_secoes_e_cenarios():
    fatia = _fatia(historia_ids=[10]).model_dump()
    historias_map = {
        10: {"title": "Como PO quero cadastrar", "gherkin": "Dado A", "rn_codes": ["RN-001"]}
    }
    cenarios_map = {10: [{"kind": "feliz", "gherkin": "Dado feliz"}]}
    md = renderizar_pacote("F-001", fatia, historias_map, cenarios_map)
    assert "# F-001 — Cadastro" in md
    assert "## Contrato de API proposto" in md
    assert "## Modelo de dados" in md
    assert "## UI" in md
    assert "## Definition of Done" in md
    assert "[feliz] Dado feliz" in md  # cenário injetado do banco
    assert "Como PO quero cadastrar" in md


def test_injetar_cenarios_na_leitura_substitui_placeholder():
    # pacote gerado SEM cenários (E5 ainda não rodou) → placeholder.
    fatia = _fatia(historia_ids=[7]).model_dump()
    md_sem = renderizar_pacote(
        "F-001", fatia, {7: {"title": "US", "gherkin": "G", "rn_codes": []}}, {}
    )
    assert "rode a E5" in md_sem
    # na leitura, injeta os cenários que a E5 gerou depois (parseando [id=7]).
    md_com = injetar_cenarios(md_sem, {7: [{"kind": "feliz", "gherkin": "Cenário feliz"}]})
    assert "rode a E5" not in md_com
    assert "[feliz] Cenário feliz" in md_com
    assert "## Definition of Done" in md_com  # resto do pacote intacto
    assert "## Contrato de API proposto" in md_com


# ─── persistência ──────────────────────────────────────────────────────────
def test_persistir_fatias_grava_slice_package_e_audit(session):
    project = Project(name="proj-f")
    session.add(project)
    session.flush()
    run = Run(project_id=project.id, stage="E6")
    session.add(run)
    session.flush()
    epic = Epic(run_id=run.id, title="Épico")
    session.add(epic)
    session.flush()
    story = Story(epic_id=epic.id, title="US", status="aprovada", gherkin="Dado X")
    session.add(story)
    session.flush()
    session.add(TestScenario(story_id=story.id, kind=ScenarioKind.feliz, gherkin="G"))
    session.flush()

    fatias = [
        {
            "nome": "Fatia 1",
            "historia_ids": [story.id],
            "contrato_api": "POST /x",
            "modelo_dados": "tabela x",
            "ui": "tela x",
            "roteiro_demo": ["p1"],
        }
    ]
    historias = [{"id": story.id, "title": "US", "gherkin": "Dado X", "rn_codes": []}]
    persistir_fatias(session, run.id, fatias, historias, base_dir=None)

    sl = session.scalar(select(Slice).where(Slice.run_id == run.id))
    assert sl is not None
    assert sl.code == "F-001"
    assert sl.package_md and "## Definition of Done" in sl.package_md
    entidades = set(
        session.scalars(select(AuditLog.entity).where(AuditLog.run_id == run.id))
    )
    assert "slice" in entidades
