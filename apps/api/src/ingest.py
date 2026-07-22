"""Ingestão de materiais (E1): parse → chunking.

Parse por tipo de origem (pdf/docx/md/txt/paste), preservando a origem
(página, quando disponível). Chunking em janelas com sobreposição.

O chunking é aproximado por palavras (~800 palavras, sobreposição 100) — o
PRD fala em "~800 tokens"; usamos palavras como aproximação determinística e
testável, sem depender de tokenizer externo. Ajustável se preciso.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

import docx
from pypdf import PdfReader

CHUNK_WORDS = 800
OVERLAP_WORDS = 100


@dataclass
class ParsedBlock:
    """Um bloco de texto extraído, com a página de origem (None se n/a)."""

    text: str
    page: int | None


@dataclass
class Chunk:
    text: str
    page: int | None


def parse_material(content: bytes, source_type: str) -> list[ParsedBlock]:
    """Extrai blocos de texto do material conforme o tipo de origem.

    - pdf: um bloco por página (page = número da página, 1-based)
    - docx: um bloco único com os parágrafos concatenados (sem página)
    - md/txt/paste: um bloco único com o texto decodificado (sem página)
    """
    st = source_type.lower()
    if st == "pdf":
        reader = PdfReader(io.BytesIO(content))
        blocks = []
        for i, page in enumerate(reader.pages, start=1):
            text = (page.extract_text() or "").strip()
            if text:
                blocks.append(ParsedBlock(text=text, page=i))
        return blocks
    if st == "docx":
        document = docx.Document(io.BytesIO(content))
        text = "\n".join(p.text for p in document.paragraphs if p.text.strip())
        return [ParsedBlock(text=text, page=None)] if text.strip() else []
    # md / txt / paste
    text = content.decode("utf-8", errors="replace").strip()
    return [ParsedBlock(text=text, page=None)] if text else []


def chunk_text(
    text: str,
    page: int | None = None,
    chunk_words: int = CHUNK_WORDS,
    overlap_words: int = OVERLAP_WORDS,
) -> list[Chunk]:
    """Divide um texto em janelas de palavras com sobreposição.

    Determinístico: mesmas entradas → mesmos chunks. Preserva a página.
    """
    words = text.split()
    if not words:
        return []
    if len(words) <= chunk_words:
        return [Chunk(text=" ".join(words), page=page)]

    step = max(1, chunk_words - overlap_words)
    chunks: list[Chunk] = []
    for start in range(0, len(words), step):
        window = words[start : start + chunk_words]
        chunks.append(Chunk(text=" ".join(window), page=page))
        if start + chunk_words >= len(words):
            break
    return chunks


def parse_and_chunk(content: bytes, source_type: str) -> list[Chunk]:
    """Pipeline completo de parse + chunking para um material."""
    chunks: list[Chunk] = []
    for block in parse_material(content, source_type):
        chunks.extend(chunk_text(block.text, page=block.page))
    return chunks
