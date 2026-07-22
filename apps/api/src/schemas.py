"""Schemas Pydantic de entrada/saída da API (Fase 2)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ProjectIn(BaseModel):
    name: str


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    created_at: datetime


class MaterialOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    source_type: str
    status: str
    created_at: datetime


class BuscaResultOut(BaseModel):
    content: str
    filename: str
    page: int | None
    distance: float


class AnswersIn(BaseModel):
    respostas: dict[str, str]
    encerrar: bool = False


class GrillOut(BaseModel):
    run_id: int
    status: str  # aguardando_respostas | concluido
    cobertura: dict[str, str] = {}
    perguntas: list[dict] = []
    dossie: str | None = None
