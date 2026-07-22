"""Auth por token na API — Fase 8 / PRD §6-Segurança.

Um token estático no header `X-API-Token`, comparado a `API_TOKEN`. Exigido em
todas as rotas do router (o /health fica aberto, é do app). Vazio = auth
desligada (dev), para o fluxo local não exigir header.
"""

from __future__ import annotations

from fastapi import Header, HTTPException

from .config import settings


def require_token(x_api_token: str | None = Header(default=None)) -> None:
    """Bloqueia (401) se API_TOKEN está setado e o header não bate. No-op em dev."""
    if not settings.api_token:
        return
    if x_api_token != settings.api_token:
        raise HTTPException(status_code=401, detail="token de API inválido ou ausente")
