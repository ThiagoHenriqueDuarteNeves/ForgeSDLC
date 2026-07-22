"""Teste de integração da rag_busca — usa o banco e embeddings reais.

Não usa LLM (embeddings são determinísticos). Requer o Postgres de pé
(docker compose up -d db). Insere dados numa transação e faz rollback ao
fim, para não deixar resíduo no banco.
"""

import pytest

from src.db import SessionLocal
from src.embeddings import embed_texts
from src.models import Chunk, Material, MaterialStatus, Project
from src.tools.rag_busca import rag_busca


@pytest.fixture
def session():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


def test_rag_busca_retorna_chunk_certo_com_origem(session):
    project = Project(name="proj-teste-rag")
    session.add(project)
    session.flush()

    material = Material(
        project_id=project.id,
        filename="dossie.txt",
        source_type="txt",
        status=MaterialStatus.processado,
    )
    session.add(material)
    session.flush()

    textos = [
        "O gato é um animal felino doméstico que ronrona.",
        "O motor a combustão queima gasolina para gerar movimento.",
        "Python é uma linguagem de programação de alto nível.",
    ]
    vetores = embed_texts(textos)
    for i, (t, v) in enumerate(zip(textos, vetores, strict=True), start=1):
        session.add(
            Chunk(material_id=material.id, content=t, embedding=v, page=i)
        )
    session.flush()

    resultados = rag_busca(
        consulta="animais felinos que ronronam",
        project_id=project.id,
        session=session,
        k=1,
    )

    assert len(resultados) == 1
    r = resultados[0]
    assert "felino" in r.content  # o chunk do gato é o mais próximo
    assert r.filename == "dossie.txt"  # origem preservada
    assert r.page == 1
