"""Embeddings locais via fastembed (ONNX).

Modelo all-MiniLM-L6-v2, 384 dimensões — mesmo modelo do PRD, rodado por
ONNX Runtime em vez de PyTorch (ver docs/adr/ADR-001).

O modelo é carregado sob demanda (singleton preguiçoso) para não pesar no
import nem nos testes que não usam embedding.
"""

from __future__ import annotations

from functools import lru_cache

from fastembed import TextEmbedding

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIM = 384


@lru_cache(maxsize=1)
def _model() -> TextEmbedding:
    return TextEmbedding(model_name=MODEL_NAME)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Gera embeddings para uma lista de textos (ordem preservada)."""
    if not texts:
        return []
    return [vec.tolist() for vec in _model().embed(texts)]


def embed_query(text: str) -> list[float]:
    """Embedding de uma única consulta (usado pela tool rag_busca)."""
    return embed_texts([text])[0]
