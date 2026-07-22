"""Ponto de entrada da API do Forge SDLC.

Fase 1a: apenas GET /health e CORS para a web em dev. A checagem de banco
entra na Fase 1b, quando o Postgres subir no docker compose.
"""

from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text

from .budget import BudgetExceeded
from .config import settings
from .db import engine
from .observability import clear_run, configure_logging
from .ratelimit import RateLimitMiddleware
from .routes import router

configure_logging()

app = FastAPI(title=settings.app_name, version=settings.app_version)

# Rate limit por IP (Fase 8). No-op quando RATE_LIMIT_PER_MIN=0.
app.add_middleware(RateLimitMiddleware)


@app.middleware("http")
async def _reset_log_context(request: Request, call_next):
    """Zera o contexto de log por request para o run_id/estágio não vazar de
    uma execução para outra no mesmo worker."""
    clear_run()
    return await call_next(request)


@app.exception_handler(BudgetExceeded)
async def _budget_exceeded_handler(request: Request, exc: BudgetExceeded) -> JSONResponse:
    """Run estourou o orçamento: marca como abortado e devolve 402 à UI."""
    if exc.run_id is not None:
        from .models import RunStatus

        with engine.begin() as conn:
            conn.execute(
                text("UPDATE runs SET status = :s WHERE id = :i"),
                {"s": RunStatus.abortado.value, "i": exc.run_id},
            )
    return JSONResponse(status_code=402, content={"detail": str(exc)})

# Em dev, a web (Next em :3000) consome a API (:8000) via browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(router)


class Health(BaseModel):
    status: str
    service: str
    version: str
    database: str


@app.get("/health", response_model=Health)
def health(response: Response) -> Health:
    """Readiness check — consumido pela home da web (primeira fatia vertical).

    Verifica o banco (SELECT 1). Se o Postgres estiver inacessível, responde
    503 com database="down" — o healthcheck do container reflete o banco.
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        database = "up"
    except Exception:
        database = "down"
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return Health(
        status="ok" if database == "up" else "degraded",
        service=settings.app_name,
        version=settings.app_version,
        database=database,
    )
