"""Carregamento dos prompts dos agentes de instructions/*.md.

REGRA (CLAUDE.md): prompts vivem em instructions/*.md, nunca hardcodados.
Mudança de prompt = mudança de comportamento = PR.
"""

from __future__ import annotations

from functools import cache
from pathlib import Path

from .config import settings


def _candidate_dirs() -> list[Path]:
    dirs: list[Path] = []
    if settings.instructions_dir:
        dirs.append(Path(settings.instructions_dir))
    # Raiz do repo ao rodar de apps/api/src (parents: src→api→apps→repo).
    # No container o caminho é mais raso (/app/src) — daí o guard.
    parents = Path(__file__).resolve().parents
    if len(parents) > 3:
        dirs.append(parents[3] / "instructions")
    # Dentro do container (volume monta em /app/instructions).
    dirs.append(Path("/app/instructions"))
    dirs.append(Path.cwd() / "instructions")
    return dirs


@cache
def load_instructions(name: str) -> str:
    """Lê instructions/<name>.md e retorna o conteúdo.

    `name` sem extensão (ex.: 'grill_me'). Levanta FileNotFoundError se o
    arquivo não existir em nenhum diretório candidato.
    """
    filename = name if name.endswith(".md") else f"{name}.md"
    for base in _candidate_dirs():
        path = base / filename
        if path.is_file():
            return path.read_text(encoding="utf-8")
    raise FileNotFoundError(
        f"instrução '{filename}' não encontrada em: {[str(d) for d in _candidate_dirs()]}"
    )
