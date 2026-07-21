"""Ponto de entrada da API do Forge SDLC.

Fase 1a: apenas GET /health e CORS para a web em dev. A checagem de banco
entra na Fase 1b, quando o Postgres subir no docker compose.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .config import settings

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


@app.get("/health", response_model=Health)
def health() -> Health:
    """Liveness check — consumido pela home da web (primeira fatia vertical)."""
    return Health(status="ok", service=settings.app_name, version=settings.app_version)
