"""Critérios de aceite da Fase 5 (E5).

- validador puro: ≥3 cenários cobrindo feliz/alternativo/erro;
- persistência: ADR + cenários + auditoria;
- cenário sem história de origem é IMPOSSÍVEL (FK NOT NULL no banco).
"""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.agents.arquitetura import cenarios_suficientes
from src.agents.schemas import Cenario, CenariosDaHistoria
from src.db import engine
from src.models import Adr, AuditLog, Epic, Project, Run, ScenarioKind, Story, TestScenario
from src.services_regras import persistir_e5


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


def _cen(categoria: str) -> Cenario:
    return Cenario(
        nome=f"cenário {categoria}",
        categoria=categoria,
        nivel="integracao",
        gherkin="Dado X\nQuando Y\nEntão Z",
        rns=["RN-001"],
    )


# ─── validador puro ────────────────────────────────────────────────────────
def test_cenarios_suficientes_ok_com_as_3_categorias():
    c = CenariosDaHistoria(cenarios=[_cen("feliz"), _cen("alternativo"), _cen("erro")])
    assert cenarios_suficientes(c) is True


def test_cenarios_insuficientes_faltando_categoria():
    c = CenariosDaHistoria(cenarios=[_cen("feliz"), _cen("feliz"), _cen("feliz")])
    assert cenarios_suficientes(c) is False  # 3, mas sem alternativo/erro


def test_cenarios_insuficientes_menos_de_3():
    c = CenariosDaHistoria(cenarios=[_cen("feliz"), _cen("erro")])
    assert cenarios_suficientes(c) is False


# ─── persistência ──────────────────────────────────────────────────────────
def _story(session) -> tuple[int, Story]:
    project = Project(name="proj-e5")
    session.add(project)
    session.flush()
    run = Run(project_id=project.id, stage="E5")
    session.add(run)
    session.flush()
    epic = Epic(run_id=run.id, title="Épico")
    session.add(epic)
    session.flush()
    story = Story(epic_id=epic.id, title="US aprovada", status="aprovada")
    session.add(story)
    session.flush()
    return run.id, story


def test_persistir_e5_grava_adr_cenarios_e_auditoria(session):
    run_id, story = _story(session)
    adr = {
        "contexto": "alto volume",
        "opcoes": [{"stack": "FastAPI+PG", "pros": "simples", "contras": "-"}],
        "decisao": "FastAPI + Postgres",
        "consequencias": ["operação simples"],
    }
    def cen(cat: str) -> dict:
        return {"nome": cat, "categoria": cat, "nivel": "unit", "gherkin": "G", "rns": []}

    grupos = [
        {
            "story_id": story.id,
            "cenarios": [cen("feliz"), cen("alternativo"), cen("erro")],
        }
    ]
    persistir_e5(session, run_id, adr, grupos)

    assert session.scalar(Adr.__table__.select().where(Adr.run_id == run_id)) is not None
    cenarios = list(
        session.scalars(
            TestScenario.__table__.select().where(TestScenario.story_id == story.id)
        )
    )
    assert len(cenarios) == 3
    acoes = set(
        session.scalars(
            AuditLog.__table__.select()
            .with_only_columns(AuditLog.entity)
            .where(AuditLog.run_id == run_id)
        )
    )
    assert {"adr", "test_scenario"} <= acoes


def test_cenario_sem_historia_e_impossivel(session):
    # FK story_id é NOT NULL: cenário órfão não entra no banco.
    session.add(TestScenario(story_id=None, kind=ScenarioKind.feliz, gherkin="x"))
    with pytest.raises(IntegrityError):
        session.flush()
