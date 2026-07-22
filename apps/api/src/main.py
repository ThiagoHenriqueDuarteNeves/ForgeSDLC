"""Ponto de entrada da API do Forge SDLC.

Fase 1a: apenas GET /health e CORS para a web em dev. A checagem de banco
entra na Fase 1b, quando o Postgres subir no docker compose.
"""

from fastapi import FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import text

from .config import settings
from .db import engine

app = FastAPI(title=settings.app_name, version=settings.app_version)

# Em dev, a web (Next em :3000) consome a API (:8000) via browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


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
