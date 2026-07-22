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


class DossieOut(BaseModel):
    run_id: int
    dossie: str | None = None


class GrillQAOut(BaseModel):
    question: str
    answer: str | None = None
    item_checklist: str | None = None


class GrillHistoricoOut(BaseModel):
    run_id: int
    status: str | None = None
    qa: list[GrillQAOut] = []


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


# ─── E5: ADR + cenários de teste ──────────────────────────────────────────
class AdrOut(BaseModel):
    title: str
    context: str
    options: str
    decision: str
    consequences: str


class CenarioOut(BaseModel):
    kind: str  # feliz | alternativo | erro
    gherkin: str


class HistoriaCenariosOut(BaseModel):
    story_id: int
    title: str
    cenarios: list[CenarioOut] = []


class E5Out(BaseModel):
    run_id: int
    status: str  # pendente | concluido
    adr: AdrOut | None = None
    historias: list[HistoriaCenariosOut] = []


# ─── E6: fatias verticais ─────────────────────────────────────────────────
class FatiaOut(BaseModel):
    code: str
    title: str
    status: str  # planejada | em_dev | entregue
    package_path: str | None = None
    package_md: str | None = None


class FatiasOut(BaseModel):
    run_id: int
    status: str  # pendente | concluido
    fatias: list[FatiaOut] = []


class StatusFatiaIn(BaseModel):
    status: str  # planejada | em_dev | entregue


# ─── Observabilidade: métricas por estágio (Fase 7) ───────────────────────
class EstagioMetricaOut(BaseModel):
    stage: str  # E2..E6
    chamadas: int
    tokens_in: int
    tokens_out: int
    cost_usd: float
    latency_ms: int


class TotalMetricaOut(BaseModel):
    chamadas: int
    tokens_in: int
    tokens_out: int
    cost_usd: float
    latency_ms: int


class RunMetricasOut(BaseModel):
    run_id: int
    estagios: list[EstagioMetricaOut] = []
    total: TotalMetricaOut


class RunResumoMetricaOut(BaseModel):
    run_id: int
    chamadas: int
    cost_usd: float
    latency_ms: int


class MetricasAgregadoOut(BaseModel):
    estagios: list[EstagioMetricaOut] = []
    runs: list[RunResumoMetricaOut] = []
    total: TotalMetricaOut
