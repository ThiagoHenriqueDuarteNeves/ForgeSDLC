"""Fatia-exemplo F-EX01 (E7): anotações do projeto, ponta a ponta na API.

Integração via TestClient contra o banco real (como test_health). Cobre os
cenários do pacote da fatia: feliz (criar→listar), alternativo (lista vazia) e
erro (texto vazio → 422; projeto inexistente → 404). Limpa o que cria.
"""

from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


def _novo_projeto() -> int:
    resp = client.post("/projects", json={"name": "proj-anotacoes-teste"})
    assert resp.status_code == 201
    return resp.json()["id"]


def _apagar_projeto(project_id: int) -> None:
    # Limpeza best-effort: remove notas + projeto criados pelo teste.
    from sqlalchemy import delete

    from src.db import SessionLocal
    from src.models import Project, ProjectNote

    s = SessionLocal()
    try:
        s.execute(delete(ProjectNote).where(ProjectNote.project_id == project_id))
        s.execute(delete(Project).where(Project.id == project_id))
        s.commit()
    finally:
        s.close()


def test_criar_e_listar_anotacao():
    pid = _novo_projeto()
    try:
        # alternativo: projeto sem anotações → lista vazia
        assert client.get(f"/projects/{pid}/notes").json() == []

        # feliz: cria e passa a aparecer
        r1 = client.post(f"/projects/{pid}/notes", json={"text": "primeira nota"})
        assert r1.status_code == 201
        assert r1.json()["text"] == "primeira nota"

        client.post(f"/projects/{pid}/notes", json={"text": "segunda nota"})
        lista = client.get(f"/projects/{pid}/notes").json()
        assert [n["text"] for n in lista] == ["segunda nota", "primeira nota"]  # nova no topo
    finally:
        _apagar_projeto(pid)


def test_anotacao_vazia_e_rejeitada():
    pid = _novo_projeto()
    try:
        assert client.post(f"/projects/{pid}/notes", json={"text": ""}).status_code == 422
        assert client.post(f"/projects/{pid}/notes", json={"text": "   "}).status_code == 422
    finally:
        _apagar_projeto(pid)


def test_projeto_inexistente_404():
    assert client.get("/projects/99999999/notes").status_code == 404
    assert (
        client.post("/projects/99999999/notes", json={"text": "x"}).status_code == 404
    )
