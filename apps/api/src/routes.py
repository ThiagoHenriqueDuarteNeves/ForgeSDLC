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

from .auth import require_token
from .config import settings
from .db import get_session
from .graph.e5_pipeline import get_e5, start_e5
from .graph.fatias_pipeline import get_fatias, start_fatias
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
from .ingest import pdf_page_count
from .metrics import metrics_agregado, metrics_por_run
from .models import (
    GrillQA,
    GrillSession,
    Material,
    MaterialStatus,
    Project,
    Run,
    RunStatus,
)
from .schemas import (
    AnswersIn,
    BuscaResultOut,
    ContestacaoOut,
    DecisoesIn,
    DossieOut,
    E5Out,
    FatiasOut,
    GrillHistoricoOut,
    GrillOut,
    GrillQAOut,
    HistoriasOut,
    MaterialOut,
    MetricasAgregadoOut,
    ProjectIn,
    ProjectOut,
    RegrasOut,
    RespostasContestacaoIn,
    RunMetricasOut,
    StatusFatiaIn,
)
from .services import process_material
from .services_regras import atualizar_status_fatia
from .tools.rag_busca import rag_busca

# Auth por token vale para todo o router (o /health, no app, fica aberto).
router = APIRouter(dependencies=[Depends(require_token)])

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
        # Limite de páginas por PDF (PRD §4/E1) — rejeita, nunca trunca calado.
        if source_type == "pdf" and settings.max_pages_per_file > 0:
            paginas = pdf_page_count(content)
            if paginas > settings.max_pages_per_file:
                raise HTTPException(
                    status_code=413,
                    detail=(
                        f"PDF com {paginas} páginas excede o limite de "
                        f"{settings.max_pages_per_file}"
                    ),
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
    # 1 run ativo por projeto (PRD §4/E1): bloqueia entrevistas concorrentes.
    ativo = session.scalar(
        select(Run.id)
        .where(Run.project_id == project_id, Run.status == RunStatus.em_andamento)
        .limit(1)
    )
    if ativo is not None:
        raise HTTPException(
            status_code=409,
            detail=f"projeto já tem um run ativo (#{ativo}); conclua-o antes de iniciar outro",
        )
    return GrillOut(**start_grill(project_id))


@router.get("/runs/{run_id}", response_model=GrillOut)
def obter_run(run_id: int) -> GrillOut:
    """Estado atual do run: perguntas pendentes ou dossiê."""
    return GrillOut(**get_grill(run_id))


@router.post("/runs/{run_id}/answers", response_model=GrillOut)
def responder_run(run_id: int, body: AnswersIn) -> GrillOut:
    """Envia as respostas da rodada e retoma o grafo."""
    return GrillOut(**answer_grill(run_id, body.respostas, body.encerrar))


@router.get("/runs/{run_id}/dossie", response_model=DossieOut)
def obter_dossie(run_id: int, session: Session = Depends(get_session)) -> DossieOut:
    """Dossiê persistido em domínio (runs.dossie)."""
    run = session.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run não encontrado")
    return DossieOut(run_id=run_id, dossie=run.dossie)


@router.get("/runs/{run_id}/grill", response_model=GrillHistoricoOut)
def obter_historico_grill(
    run_id: int, session: Session = Depends(get_session)
) -> GrillHistoricoOut:
    """Histórico da entrevista (grill_sessions + grill_qa)."""
    gs = session.scalar(select(GrillSession).where(GrillSession.run_id == run_id))
    if gs is None:
        return GrillHistoricoOut(run_id=run_id, status=None, qa=[])
    qa = session.scalars(
        select(GrillQA).where(GrillQA.grill_session_id == gs.id).order_by(GrillQA.id)
    )
    return GrillHistoricoOut(
        run_id=run_id,
        status=gs.status,
        qa=[
            GrillQAOut(
                question=q.question, answer=q.answer, item_checklist=q.item_checklist
            )
            for q in qa
        ],
    )


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


# ─── E5: arquiteto de stack ∥ designer de testes ──────────────────────────
@router.post("/runs/{run_id}/e5", response_model=E5Out, status_code=201)
def rodar_e5(run_id: int) -> E5Out:
    """Roda os ramos paralelos (ADR + cenários); exige histórias aprovadas."""
    try:
        return E5Out(**start_e5(run_id))
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


@router.get("/runs/{run_id}/e5", response_model=E5Out)
def obter_e5(run_id: int) -> E5Out:
    return E5Out(**get_e5(run_id))


# ─── E6: fatiador vertical ────────────────────────────────────────────────
@router.post("/runs/{run_id}/fatias", response_model=FatiasOut, status_code=201)
def rodar_fatias(run_id: int) -> FatiasOut:
    """Agrupa histórias aprovadas em fatias verticais; exige histórias aprovadas."""
    try:
        return FatiasOut(**start_fatias(run_id))
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


@router.get("/runs/{run_id}/fatias", response_model=FatiasOut)
def obter_fatias(run_id: int) -> FatiasOut:
    return FatiasOut(**get_fatias(run_id))


@router.patch("/runs/{run_id}/fatias/{code}", response_model=FatiasOut)
def status_fatia(
    run_id: int,
    code: str,
    body: StatusFatiaIn,
    session: Session = Depends(get_session),
) -> FatiasOut:
    """Muda o status de uma fatia (planejada/em_dev/entregue)."""
    try:
        sl = atualizar_status_fatia(session, run_id, code, body.status)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if sl is None:
        raise HTTPException(status_code=404, detail="fatia não encontrada")
    return FatiasOut(**get_fatias(run_id))


# ─── Observabilidade: métricas por estágio (Fase 7) ───────────────────────
@router.get("/runs/{run_id}/metrics", response_model=RunMetricasOut)
def metricas_run(
    run_id: int, session: Session = Depends(get_session)
) -> RunMetricasOut:
    """Custo e tempo por estágio de um run (quanto custou, onde foi o tempo)."""
    return RunMetricasOut(**metrics_por_run(session, run_id))


@router.get("/metrics", response_model=MetricasAgregadoOut)
def metricas_agregado(
    session: Session = Depends(get_session),
) -> MetricasAgregadoOut:
    """Visão agregada: totais por estágio e por run (todos os runs)."""
    return MetricasAgregadoOut(**metrics_agregado(session))
