"""Modelos do banco — tabelas do PRD §5 (fonte de verdade do schema).

Decisões da entrevista Grill Me refletidas aqui:
- business_rules imutável: status inclui `contestada` e `superseded`, com
  auto-referência `supersedes` (PRD §4/E3.1).
- users + role e audit_log presentes desde a fundação (PRD §5/§6).
- stories.stale marca artefatos derivados de RN superada.
"""

from __future__ import annotations

import enum
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Base

# Dimensão dos embeddings (sentence-transformers/all-MiniLM-L6-v2).
EMBEDDING_DIM = 384


# ─── Enums ────────────────────────────────────────────────────────────────
class MaterialStatus(enum.StrEnum):
    pendente = "pendente"
    processando = "processando"
    processado = "processado"
    erro = "erro"


class RunStatus(enum.StrEnum):
    em_andamento = "em_andamento"
    pausado = "pausado"
    concluido = "concluido"
    abortado = "abortado"


class RuleStatus(enum.StrEnum):
    proposta = "proposta"
    aprovada = "aprovada"
    rejeitada = "rejeitada"
    contestada = "contestada"
    superseded = "superseded"


class UserRole(enum.StrEnum):
    po = "po"
    qa = "qa"
    dev = "dev"
    admin = "admin"


class ScenarioKind(enum.StrEnum):
    feliz = "feliz"
    alternativo = "alternativo"
    erro = "erro"


class SliceStatus(enum.StrEnum):
    planejada = "planejada"
    em_dev = "em_dev"
    entregue = "entregue"


def _ts() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now())


# ─── Núcleo: projetos, materiais, chunks ──────────────────────────────────
class Project(Base):
    __tablename__ = "projects"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(256))
    created_at: Mapped[datetime] = _ts()

    materials: Mapped[list[Material]] = relationship(back_populates="project")
    runs: Mapped[list[Run]] = relationship(back_populates="project")


class Material(Base):
    __tablename__ = "materials"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    filename: Mapped[str] = mapped_column(String(512))
    source_type: Mapped[str] = mapped_column(String(32))  # pdf/docx/md/txt/paste
    status: Mapped[MaterialStatus] = mapped_column(
        Enum(MaterialStatus), default=MaterialStatus.pendente
    )
    created_at: Mapped[datetime] = _ts()

    project: Mapped[Project] = relationship(back_populates="materials")
    chunks: Mapped[list[Chunk]] = relationship(back_populates="material")


class Chunk(Base):
    __tablename__ = "chunks"
    id: Mapped[int] = mapped_column(primary_key=True)
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id"))
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM))
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = _ts()

    material: Mapped[Material] = relationship(back_populates="chunks")


# ─── Execução do pipeline ─────────────────────────────────────────────────
class Run(Base):
    __tablename__ = "runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    stage: Mapped[str] = mapped_column(String(32))  # E1..E7
    graph_state: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[RunStatus] = mapped_column(
        Enum(RunStatus), default=RunStatus.em_andamento
    )
    created_at: Mapped[datetime] = _ts()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    project: Mapped[Project] = relationship(back_populates="runs")


# ─── Grill Me ─────────────────────────────────────────────────────────────
class GrillSession(Base):
    __tablename__ = "grill_sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"))
    status: Mapped[str] = mapped_column(String(32), default="ativa")
    created_at: Mapped[datetime] = _ts()

    qa: Mapped[list[GrillQA]] = relationship(back_populates="session")


class GrillQA(Base):
    __tablename__ = "grill_qa"
    id: Mapped[int] = mapped_column(primary_key=True)
    grill_session_id: Mapped[int] = mapped_column(ForeignKey("grill_sessions.id"))
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    item_checklist: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = _ts()

    session: Mapped[GrillSession] = relationship(back_populates="qa")


# ─── Regras de negócio (imutáveis) ────────────────────────────────────────
class BusinessRule(Base):
    __tablename__ = "business_rules"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"))
    code: Mapped[str] = mapped_column(String(16))  # RN-001
    text: Mapped[str] = mapped_column(Text)
    fonte: Mapped[str] = mapped_column(Text)  # obrigatória (PRD)
    status: Mapped[RuleStatus] = mapped_column(
        Enum(RuleStatus), default=RuleStatus.proposta
    )
    supersedes_id: Mapped[int | None] = mapped_column(
        ForeignKey("business_rules.id"), nullable=True
    )
    # Motivo da contestação (RN errada) ou justificativa de um supersede.
    motivo: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = _ts()

    __table_args__ = (UniqueConstraint("run_id", "code", name="uq_rule_code_per_run"),)


# ─── Histórias e rastreabilidade ──────────────────────────────────────────
class Epic(Base):
    __tablename__ = "epics"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"))
    title: Mapped[str] = mapped_column(String(512))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = _ts()

    stories: Mapped[list[Story]] = relationship(back_populates="epic")


class Story(Base):
    __tablename__ = "stories"
    id: Mapped[int] = mapped_column(primary_key=True)
    epic_id: Mapped[int] = mapped_column(ForeignKey("epics.id"))
    title: Mapped[str] = mapped_column(String(512))
    gherkin: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="proposta")
    stale: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = _ts()

    epic: Mapped[Epic] = relationship(back_populates="stories")
    scenarios: Mapped[list[TestScenario]] = relationship(back_populates="story")


class StoryRule(Base):
    """Matriz de rastreabilidade RN ↔ US (many-to-many)."""

    __tablename__ = "story_rules"
    story_id: Mapped[int] = mapped_column(ForeignKey("stories.id"), primary_key=True)
    business_rule_id: Mapped[int] = mapped_column(
        ForeignKey("business_rules.id"), primary_key=True
    )


# ─── E5: ADR e cenários de teste ──────────────────────────────────────────
class Adr(Base):
    __tablename__ = "adrs"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"))
    title: Mapped[str] = mapped_column(String(512))
    context: Mapped[str] = mapped_column(Text)
    options: Mapped[str] = mapped_column(Text)
    decision: Mapped[str] = mapped_column(Text)
    consequences: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = _ts()


class TestScenario(Base):
    __tablename__ = "test_scenarios"
    id: Mapped[int] = mapped_column(primary_key=True)
    story_id: Mapped[int] = mapped_column(ForeignKey("stories.id"))
    kind: Mapped[ScenarioKind] = mapped_column(Enum(ScenarioKind))
    gherkin: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = _ts()

    story: Mapped[Story] = relationship(back_populates="scenarios")


# ─── E6: fatias verticais ─────────────────────────────────────────────────
class Slice(Base):
    __tablename__ = "slices"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"))
    code: Mapped[str] = mapped_column(String(16))  # F-001
    title: Mapped[str] = mapped_column(String(512))
    status: Mapped[SliceStatus] = mapped_column(
        Enum(SliceStatus), default=SliceStatus.planejada
    )
    package_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = _ts()


# ─── Usuários e auditoria (PRD §5/§6) ─────────────────────────────────────
class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(256), unique=True)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.po)
    created_at: Mapped[datetime] = _ts()


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(64))
    entity: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    before: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    after: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    run_id: Mapped[int | None] = mapped_column(ForeignKey("runs.id"), nullable=True)
    ts: Mapped[datetime] = _ts()
