"""Endpoints REST da Fase 2 (E1): projetos, materiais e busca."""

from __future__ import annotations

import os

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .db import get_session
from .graph.historias_pipeline import (
    aprovar_historias,
    get_historias,
    start_historias,
)
from .graph.pipeline import answer_grill, get_grill, start_grill
from .graph.regras_pipeline import (
    aprovar_regras,
    contestacao_perguntas,
    get_regras,
    resolver_contestacao_run,
    start_regras,
)
from .models import Material, MaterialStatus, Project
from .schemas import (
    AnswersIn,
    BuscaResultOut,
    ContestacaoOut,
    DecisoesIn,
    GrillOut,
    HistoriasOut,
    MaterialOut,
    ProjectIn,
    ProjectOut,
    RegrasOut,
    RespostasContestacaoIn,
)
from .services import process_material
from .tools.rag_busca import rag_busca

router = APIRouter()

# Limites duros do PRD §4/E1.
MAX_FILE_BYTES = 25 * 1024 * 1024  # 25 MB
MAX_MATERIALS_PER_PROJECT = 50

_EXT_TO_SOURCE = {".pdf": "pdf", ".docx": "docx", ".md": "md", ".txt": "txt"}


# ─── Projetos ─────────────────────────────────────────────────────────────
@router.post("/projects", response_model=ProjectOut, status_code=201)
def create_project(body: ProjectIn, session: Session = Depends(get_session)) -> Project:
    project = Project(name=body.name)
    session.add(project)
    session.commit()
    session.refresh(project)
    return project


@router.get("/projects", response_model=list[ProjectOut])
def list_projects(session: Session = Depends(get_session)) -> list[Project]:
    return list(session.execute(select(Project).order_by(Project.id)).scalars())


# ─── Materiais ────────────────────────────────────────────────────────────
def _require_project(session: Session, project_id: int) -> Project:
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="projeto não encontrado")
    return project


@router.post(
    "/projects/{project_id}/materials", response_model=MaterialOut, status_code=201
)
async def add_material(
    project_id: int,
    background: BackgroundTasks,
    file: UploadFile | None = File(default=None),
    text: str | None = Form(default=None),
    session: Session = Depends(get_session),
) -> Material:
    _require_project(session, project_id)

    count = session.scalar(
        select(func.count()).select_from(Material).where(Material.project_id == project_id)
    )
    if count is not None and count >= MAX_MATERIALS_PER_PROJECT:
        raise HTTPException(
            status_code=409,
            detail=f"limite de {MAX_MATERIALS_PER_PROJECT} materiais por projeto atingido",
        )

    if file is not None:
        content = await file.read()
        filename = file.filename or "arquivo"
        ext = os.path.splitext(filename)[1].lower()
        source_type = _EXT_TO_SOURCE.get(ext)
        if source_type is None:
            raise HTTPException(
                status_code=415, detail=f"tipo não suportado: {ext or '(sem extensão)'}"
            )
    elif text is not None and text.strip():
        content = text.encode("utf-8")
        filename = "texto colado"
        source_type = "paste"
    else:
        raise HTTPException(status_code=400, detail="envie um arquivo ou um texto")

    if len(content) > MAX_FILE_BYTES:
        raise HTTPException(
            status_code=413, detail="arquivo excede o limite de 25 MB"
        )

    material = Material(
        project_id=project_id,
        filename=filename,
        source_type=source_type,
        status=MaterialStatus.pendente,
    )
    session.add(material)
    session.commit()
    session.refresh(material)

    background.add_task(process_material, material.id, content, source_type)
    return material


@router.get("/projects/{project_id}/materials", response_model=list[MaterialOut])
def list_materials(
    project_id: int, session: Session = Depends(get_session)
) -> list[Material]:
    _require_project(session, project_id)
    return list(
        session.execute(
            select(Material)
            .where(Material.project_id == project_id)
            .order_by(Material.id)
        ).scalars()
    )


# ─── Busca semântica (expõe a tool rag_busca) ─────────────────────────────
@router.get("/projects/{project_id}/busca", response_model=list[BuscaResultOut])
def busca(
    project_id: int,
    q: str,
    k: int = 5,
    session: Session = Depends(get_session),
) -> list[BuscaResultOut]:
    _require_project(session, project_id)
    resultados = rag_busca(consulta=q, project_id=project_id, session=session, k=k)
    return [
        BuscaResultOut(
            content=r.content, filename=r.filename, page=r.page, distance=r.distance
        )
        for r in resultados
    ]


# ─── Grill Me (E2) ────────────────────────────────────────────────────────
@router.post("/projects/{project_id}/runs", response_model=GrillOut, status_code=201)
def criar_run(project_id: int, session: Session = Depends(get_session)) -> GrillOut:
    """Inicia uma entrevista Grill Me e retorna a primeira rodada de perguntas."""
    _require_project(session, project_id)
    return GrillOut(**start_grill(project_id))


@router.get("/runs/{run_id}", response_model=GrillOut)
def obter_run(run_id: int) -> GrillOut:
    """Estado atual do run: perguntas pendentes ou dossiê."""
    return GrillOut(**get_grill(run_id))


@router.post("/runs/{run_id}/answers", response_model=GrillOut)
def responder_run(run_id: int, body: AnswersIn) -> GrillOut:
    """Envia as respostas da rodada e retoma o grafo."""
    return GrillOut(**answer_grill(run_id, body.respostas, body.encerrar))


# ─── E3: regras de negócio ────────────────────────────────────────────────
@router.post("/runs/{run_id}/regras", response_model=RegrasOut, status_code=201)
def extrair_regras_run(run_id: int) -> RegrasOut:
    """Roda o subgrafo E3 (extração + refino) até o gate de aprovação."""
    try:
        return RegrasOut(**start_regras(run_id))
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


@router.get("/runs/{run_id}/regras", response_model=RegrasOut)
def obter_regras_run(run_id: int) -> RegrasOut:
    return RegrasOut(**get_regras(run_id))


@router.post("/runs/{run_id}/regras/decisoes", response_model=RegrasOut)
def decidir_regras_run(run_id: int, body: DecisoesIn) -> RegrasOut:
    """Aplica aprovar/rejeitar/contestar por RN e retoma o grafo."""
    return RegrasOut(**aprovar_regras(run_id, body.decisoes, body.motivos))


@router.get(
    "/runs/{run_id}/regras/{code}/contestacao", response_model=ContestacaoOut
)
def perguntas_contestacao_run(run_id: int, code: str) -> ContestacaoOut:
    """Abre a rodada dirigida do Grill Me sobre a lacuna de uma RN contestada."""
    try:
        return ContestacaoOut(**contestacao_perguntas(run_id, code))
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


@router.post("/runs/{run_id}/regras/{code}/contestacao", response_model=RegrasOut)
def resolver_contestacao_endpoint(
    run_id: int, code: str, body: RespostasContestacaoIn
) -> RegrasOut:
    """Resolve a contestação: cria RN nova (supersede) e supera a original."""
    try:
        return RegrasOut(**resolver_contestacao_run(run_id, code, body.respostas))
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


# ─── E4: épicos e histórias ───────────────────────────────────────────────
@router.post("/runs/{run_id}/historias", response_model=HistoriasOut, status_code=201)
def gerar_historias_run(run_id: int) -> HistoriasOut:
    """Roda a E4 (analista) até o gate de aprovação; exige RNs aprovadas."""
    try:
        return HistoriasOut(**start_historias(run_id))
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


@router.get("/runs/{run_id}/historias", response_model=HistoriasOut)
def obter_historias_run(run_id: int) -> HistoriasOut:
    return HistoriasOut(**get_historias(run_id))


@router.post("/runs/{run_id}/historias/decisoes", response_model=HistoriasOut)
def decidir_historias_run(run_id: int, body: DecisoesIn) -> HistoriasOut:
    """Aplica aprovar/rejeitar por história e retoma o grafo."""
    return HistoriasOut(**aprovar_historias(run_id, body.decisoes))
