"""Rate limit por IP (janela deslizante em memória) — Fase 8 / PRD §6.

Simples e sem dependência externa: uma fila de timestamps por IP, corte de 60s.
No-op quando `RATE_LIMIT_PER_MIN=0` (dev). O /health nunca é limitado (o
healthcheck do container bate nele). Em processo único é suficiente para v1;
um deploy multi-worker trocaria por um store compartilhado (Redis).
"""

from __future__ import annotations

import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from .config import settings


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app) -> None:
        super().__init__(app)
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next):
        limit = settings.rate_limit_per_min
        if limit <= 0 or request.url.path == "/health":
            return await call_next(request)

        ip = request.client.host if request.client else "unknown"
        now = time.monotonic()
        janela = self._hits[ip]
        while janela and now - janela[0] > 60:
            janela.popleft()
        if len(janela) >= limit:
            return JSONResponse(
                status_code=429,
                content={"detail": "rate limit excedido; tente em instantes"},
            )
        janela.append(now)
        return await call_next(request)
