"""Tool de recuperação semântica sobre o corpus de um projeto.

Esta tool é lida pelos agentes (o docstring importa): dada uma consulta em
linguagem natural e um projeto, retorna os trechos (chunks) mais relevantes
do material ingerido, com a origem citável (arquivo e página).
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from ..config import settings
from ..embeddings import embed_query
from ..models import Chunk, Material
from ..security import sanitizar


@dataclass
class ResultadoBusca:
    content: str
    filename: str
    page: int | None
    distance: float


def rag_busca(
    consulta: str,
    project_id: int,
    session: Session,
    k: int = 5,
) -> list[ResultadoBusca]:
    """Busca semântica no corpus de um projeto.

    Gera o embedding da `consulta` e retorna os `k` chunks mais próximos
    (distância de cosseno no pgvector) entre os materiais do `project_id`.
    Cada resultado traz o texto do trecho e sua origem (arquivo + página),
    para que o agente cite a fonte de cada afirmação.

    Args:
        consulta: pergunta ou tópico em linguagem natural.
        project_id: projeto cujo corpus será consultado.
        session: sessão SQLAlchemy aberta.
        k: número máximo de trechos a retornar (padrão 5).

    Returns:
        Lista de ResultadoBusca ordenada do mais relevante ao menos, com
        `content`, `filename`, `page` (pode ser None) e `distance` (0 = idêntico).
    """
    query_vec = embed_query(consulta)
    stmt = (
        select(
            Chunk.content,
            Material.filename,
            Chunk.page,
            Chunk.embedding.cosine_distance(query_vec).label("distance"),
        )
        .join(Material, Chunk.material_id == Material.id)
        .where(Material.project_id == project_id)
        .order_by("distance")
        .limit(k)
    )
    # Timeout por tool (Fase 8, opt-in): corta a query no banco após N s.
    timeout_ms = settings.tool_timeout_s * 1000
    if timeout_ms > 0:
        session.execute(text("SET statement_timeout = :ms"), {"ms": timeout_ms})
    try:
        rows = session.execute(stmt).all()
    finally:
        if timeout_ms > 0:
            session.execute(text("SET statement_timeout = 0"))
    # Defesa em profundidade: re-sanitiza o trecho na saída, antes de entrar
    # em qualquer prompt (o corpus já é sanitizado na ingestão).
    return [
        ResultadoBusca(
            content=sanitizar(r.content, origem=f"rag:{r.filename}"),
            filename=r.filename,
            page=r.page,
            distance=float(r.distance),
        )
        for r in rows
    ]
