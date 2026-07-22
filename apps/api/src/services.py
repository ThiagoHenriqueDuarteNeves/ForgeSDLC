"""Serviços de ingestão executados em background (Fase 2 / E1).

process_material roda fora do request (BackgroundTask): faz parse → chunking
→ embeddings → grava chunks no pgvector, atualizando o status do material.
Abre a própria sessão (não reaproveita a do request, que já foi fechada).
"""

from __future__ import annotations

from .db import SessionLocal
from .embeddings import embed_texts
from .ingest import parse_and_chunk
from .models import Chunk, Material, MaterialStatus
from .security import sanitizar


def process_material(material_id: int, content: bytes, source_type: str) -> None:
    """Processa um material: parse → chunk → embed → grava. Atualiza status."""
    session = SessionLocal()
    try:
        material = session.get(Material, material_id)
        if material is None:
            return
        material.status = MaterialStatus.processando
        session.commit()

        chunks = parse_and_chunk(content, source_type)
        # Conteúdo NÃO CONFIÁVEL: sanitiza antes de virar corpus (neutraliza
        # injeção de prompt e redige segredos). O embedding é do texto limpo.
        texts = [sanitizar(c.text, origem=f"material:{material_id}") for c in chunks]
        vectors = embed_texts(texts)

        for chunk, text, vector in zip(chunks, texts, vectors, strict=True):
            session.add(
                Chunk(
                    material_id=material_id,
                    content=text,
                    embedding=vector,
                    page=chunk.page,
                )
            )
        material.status = MaterialStatus.processado
        session.commit()
    except Exception:
        session.rollback()
        material = session.get(Material, material_id)
        if material is not None:
            material.status = MaterialStatus.erro
            session.commit()
    finally:
        session.close()
