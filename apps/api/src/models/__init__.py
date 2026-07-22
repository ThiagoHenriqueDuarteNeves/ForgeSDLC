"""Modelos do banco (tabelas do PRD §5). Fonte de verdade do schema.

Reexporta tudo de tables.py para que o Alembic (env.py) importe a metadata
completa via `from src.models import *`.
"""

from .tables import (  # noqa: F401
    Adr,
    AuditLog,
    BusinessRule,
    Chunk,
    Epic,
    GrillQA,
    GrillSession,
    LlmCall,
    Material,
    MaterialStatus,
    Project,
    RuleStatus,
    Run,
    RunStatus,
    ScenarioKind,
    Slice,
    SliceStatus,
    Story,
    StoryRule,
    TestScenario,
    User,
    UserRole,
)
