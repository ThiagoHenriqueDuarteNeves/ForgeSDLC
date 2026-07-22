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


# ─── E3: regras de negócio ────────────────────────────────────────────────
class DecisoesIn(BaseModel):
    """code→ação (RN) ou id→ação (história). aprovar|rejeitar|contestar."""

    decisoes: dict[str, str]
    motivos: dict[str, str] = {}  # code→motivo, usado ao contestar


class ContestacaoOut(BaseModel):
    """Rodada dirigida do Grill Me sobre uma RN contestada."""

    code: str
    texto: str
    motivo: str
    perguntas: list[dict] = []


class RespostasContestacaoIn(BaseModel):
    respostas: dict[str, str]


class RegraOut(BaseModel):
    id: int
    code: str
    text: str
    fonte: str
    status: str
    motivo: str | None = None
    supersedes: str | None = None  # código da RN que esta supera


class RegrasOut(BaseModel):
    run_id: int
    status: str  # aguardando_aprovacao | concluido
    regras: list[RegraOut] = []


# ─── E4: épicos e histórias ───────────────────────────────────────────────
class EpicoOut(BaseModel):
    id: int
    title: str
    description: str | None = None


class HistoriaOut(BaseModel):
    id: int
    epic_id: int
    title: str
    gherkin: str | None = None
    status: str
    rn_codes: list[str] = []


class HistoriasOut(BaseModel):
    run_id: int
    status: str
    epicos: list[EpicoOut] = []
    historias: list[HistoriaOut] = []
