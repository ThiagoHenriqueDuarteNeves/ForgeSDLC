"""Persistência de RNs e histórias (E3/E4) com auditoria.

Regras do CLAUDE.md aplicadas aqui:
- Toda mutação de RN/história grava em `audit_log` (actor, action, entity,
  before, after, run_id).
- RN aprovada é imutável: aprovação só muda `status` (o texto nunca), e um
  trigger no banco (migração) garante isso mesmo contra UPDATE direto.
- Correção de RN = RN nova com `supersedes`; RN errada vira `contestada`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import (
    Adr,
    AuditLog,
    BusinessRule,
    Epic,
    RuleStatus,
    ScenarioKind,
    Slice,
    SliceStatus,
    Story,
    StoryRule,
    TestScenario,
    User,
    UserRole,
)


def default_user(session: Session) -> User:
    """Usuário único da v1 (PRD §5): get-or-create, sem tela de gestão."""
    user = session.scalar(select(User).where(User.email == "po@forge.local"))
    if user is None:
        user = User(email="po@forge.local", role=UserRole.po)
        session.add(user)
        session.flush()
    return user


def _audit(
    session: Session,
    *,
    actor_id: int | None,
    action: str,
    entity: str,
    entity_id: int | None,
    before: dict | None,
    after: dict | None,
    run_id: int,
) -> None:
    session.add(
        AuditLog(
            actor_id=actor_id,
            action=action,
            entity=entity,
            entity_id=entity_id,
            before=before,
            after=after,
            run_id=run_id,
        )
    )


# ─── E3: regras de negócio ────────────────────────────────────────────────
def persistir_regras(session: Session, run_id: int, regras: list[dict]) -> None:
    """Grava as RNs propostas (status=proposta). Idempotente por run."""
    ja_existe = session.scalar(
        select(BusinessRule.id).where(BusinessRule.run_id == run_id).limit(1)
    )
    if ja_existe:
        return
    actor = default_user(session)
    for r in regras:
        rn = BusinessRule(
            run_id=run_id,
            code=r["code"],
            text=r["texto"],
            fonte=r["fonte"],
            status=RuleStatus.proposta,
        )
        session.add(rn)
        session.flush()
        _audit(
            session,
            actor_id=actor.id,
            action="propor",
            entity="business_rule",
            entity_id=rn.id,
            before=None,
            after={"code": rn.code, "text": rn.text, "status": rn.status},
            run_id=run_id,
        )
    session.commit()


def aplicar_decisoes_regras(
    session: Session,
    run_id: int,
    decisoes: dict[str, str],
    motivos: dict[str, str] | None = None,
) -> None:
    """Aplica aprovar/rejeitar/contestar por código de RN, com auditoria.

    NUNCA altera o texto de uma RN (imutabilidade). Só transiciona `status`.
    `decisoes`: code -> 'aprovar' | 'rejeitar' | 'contestar'.
    `motivos`: code -> motivo (usado quando a ação é 'contestar').
    """
    motivos = motivos or {}
    actor = default_user(session)
    now = datetime.now(UTC)
    novo = {
        "aprovar": RuleStatus.aprovada,
        "rejeitar": RuleStatus.rejeitada,
        "contestar": RuleStatus.contestada,
    }
    for rn in session.scalars(
        select(BusinessRule).where(BusinessRule.run_id == run_id)
    ):
        acao = decisoes.get(rn.code)
        if acao not in novo:
            continue
        antes = {"status": rn.status}
        rn.status = novo[acao]
        if acao == "aprovar":
            rn.approved_by = actor.id
            rn.approved_at = now
        if acao == "contestar":
            rn.motivo = motivos.get(rn.code)
        _audit(
            session,
            actor_id=actor.id,
            action=acao,
            entity="business_rule",
            entity_id=rn.id,
            before=antes,
            after={"status": rn.status, "motivo": rn.motivo},
            run_id=run_id,
        )
    session.commit()


def _proximo_code(session: Session, run_id: int) -> str:
    """Próximo RN-XXX livre no run (não reusa números — append-only)."""
    maior = 0
    for (code,) in session.execute(
        select(BusinessRule.code).where(BusinessRule.run_id == run_id)
    ):
        num = code.split("-")[-1]
        if num.isdigit():
            maior = max(maior, int(num))
    return f"RN-{maior + 1:03d}"


def criar_correcao(
    session: Session, run_id: int, code_original: str, nova: dict
) -> BusinessRule:
    """Resolve uma contestação de forma append-only (PRD §4/E3.1).

    Cria uma RN NOVA que supera a contestada (`supersedes_id`), já aprovada
    (o PO acabou de resolvê-la na rodada dirigida); a original vira
    `superseded` (preservada, nunca apagada) e as histórias derivadas dela
    são marcadas `stale`. Tudo auditado.
    """
    original = session.scalar(
        select(BusinessRule).where(
            BusinessRule.run_id == run_id, BusinessRule.code == code_original
        )
    )
    if original is None:
        raise ValueError(f"RN {code_original} não encontrada no run {run_id}")
    if original.status != RuleStatus.contestada:
        raise ValueError(
            f"só se corrige RN contestada; {code_original} está {original.status}"
        )
    actor = default_user(session)
    now = datetime.now(UTC)

    nova_rn = BusinessRule(
        run_id=run_id,
        code=_proximo_code(session, run_id),
        text=nova["texto"],
        fonte=nova["fonte"],
        status=RuleStatus.aprovada,
        supersedes_id=original.id,
        motivo=f"supersede {code_original}: {original.motivo or 'contestada'}",
        approved_by=actor.id,
        approved_at=now,
    )
    session.add(nova_rn)
    session.flush()
    _audit(
        session,
        actor_id=actor.id,
        action="corrigir",
        entity="business_rule",
        entity_id=nova_rn.id,
        before={"supersedes": code_original},
        after={"code": nova_rn.code, "text": nova_rn.text, "status": nova_rn.status},
        run_id=run_id,
    )

    antes = {"status": original.status}
    original.status = RuleStatus.superseded
    _audit(
        session,
        actor_id=actor.id,
        action="superseded",
        entity="business_rule",
        entity_id=original.id,
        before=antes,
        after={"status": original.status, "por": nova_rn.code},
        run_id=run_id,
    )

    # Histórias derivadas da RN superada ficam obsoletas (nunca reprocessa só).
    story_ids = list(
        session.scalars(
            select(StoryRule.story_id).where(
                StoryRule.business_rule_id == original.id
            )
        )
    )
    if story_ids:
        for story in session.scalars(
            select(Story).where(Story.id.in_(story_ids))
        ):
            if not story.stale:
                story.stale = True
                _audit(
                    session,
                    actor_id=actor.id,
                    action="stale",
                    entity="story",
                    entity_id=story.id,
                    before={"stale": False},
                    after={"stale": True, "motivo": f"{code_original} superada"},
                    run_id=run_id,
                )
    session.commit()
    return nova_rn


def regras_aprovadas(session: Session, run_id: int) -> list[dict]:
    """RNs aprovadas do run, no formato que o analista de histórias consome."""
    rows = session.scalars(
        select(BusinessRule)
        .where(
            BusinessRule.run_id == run_id,
            BusinessRule.status == RuleStatus.aprovada,
        )
        .order_by(BusinessRule.code)
    )
    return [{"code": r.code, "texto": r.text, "tipo": "", "fonte": r.fonte} for r in rows]


# ─── E4: épicos e histórias ───────────────────────────────────────────────
def persistir_historias(session: Session, run_id: int, mapa: dict) -> None:
    """Grava épicos, histórias (status=proposta) e a matriz RN↔US. Idempotente."""
    ja_existe = session.scalar(
        select(Epic.id).where(Epic.run_id == run_id).limit(1)
    )
    if ja_existe:
        return
    actor = default_user(session)

    # code da RN -> id no banco, para montar a matriz story_rules.
    rn_id_por_code = {
        rn.code: rn.id
        for rn in session.scalars(
            select(BusinessRule).where(BusinessRule.run_id == run_id)
        )
    }
    epico_db_por_id: dict[str, Epic] = {}
    for ep in mapa.get("epicos", []):
        epic = Epic(run_id=run_id, title=ep["nome"], description=ep.get("objetivo"))
        session.add(epic)
        session.flush()
        epico_db_por_id[ep["id"]] = epic

    for h in mapa.get("historias", []):
        epic = epico_db_por_id.get(h["epico_id"])
        if epic is None:  # história sem épico válido — pendura num épico "avulso"
            epic = epico_db_por_id.get("__avulso__")
            if epic is None:
                epic = Epic(run_id=run_id, title="(sem épico)", description=None)
                session.add(epic)
                session.flush()
                epico_db_por_id["__avulso__"] = epic
        titulo = f"Como {h['ator']}, quero {h['acao']} para {h['valor']}"
        story = Story(
            epic_id=epic.id,
            title=titulo[:512],
            gherkin="\n\n".join(h.get("criterios_gherkin", [])),
            status="proposta",
        )
        session.add(story)
        session.flush()
        for code in h.get("rns_cobertas", []):
            rn_id = rn_id_por_code.get(code)
            if rn_id is not None:
                session.add(StoryRule(story_id=story.id, business_rule_id=rn_id))
        _audit(
            session,
            actor_id=actor.id,
            action="propor",
            entity="story",
            entity_id=story.id,
            before=None,
            after={"title": story.title, "rns": h.get("rns_cobertas", [])},
            run_id=run_id,
        )
    session.commit()


def historias_aprovadas(session: Session, run_id: int) -> list[dict]:
    """Histórias aprovadas do run + suas RNs (entrada do designer de testes)."""
    out: list[dict] = []
    for story in session.scalars(
        select(Story)
        .join(Epic)
        .where(Epic.run_id == run_id, Story.status == "aprovada")
        .order_by(Story.id)
    ):
        rn_codes = list(
            session.scalars(
                select(BusinessRule.code)
                .join(StoryRule, StoryRule.business_rule_id == BusinessRule.id)
                .where(StoryRule.story_id == story.id)
                .order_by(BusinessRule.code)
            )
        )
        out.append(
            {
                "id": story.id,
                "title": story.title,
                "gherkin": story.gherkin,
                "rn_codes": rn_codes,
            }
        )
    return out


def persistir_e5(
    session: Session,
    run_id: int,
    adr: dict,
    cenarios_por_historia: list[dict],
) -> None:
    """Grava o ADR e os cenários de teste (por história), com auditoria.

    Idempotente por run (não regrava se já há ADR). `cenarios_por_historia`:
    lista de {story_id, cenarios: [{nome, categoria, nivel, gherkin, rns}]}.
    """
    if session.scalar(select(Adr.id).where(Adr.run_id == run_id).limit(1)):
        return
    actor = default_user(session)

    opcoes_txt = "\n".join(
        f"- {o.get('stack', '')}\n  prós: {o.get('pros', '')}\n"
        f"  contras: {o.get('contras', '')}"
        for o in adr.get("opcoes", [])
    )
    adr_row = Adr(
        run_id=run_id,
        title="Stack do sistema-alvo (ADR)",
        context=adr.get("contexto", ""),
        options=opcoes_txt,
        decision=adr.get("decisao", ""),
        consequences="\n".join(adr.get("consequencias", [])),
    )
    session.add(adr_row)
    session.flush()
    _audit(
        session,
        actor_id=actor.id,
        action="propor",
        entity="adr",
        entity_id=adr_row.id,
        before=None,
        after={"title": adr_row.title},
        run_id=run_id,
    )

    for grupo in cenarios_por_historia:
        story_id = grupo["story_id"]
        for c in grupo.get("cenarios", []):
            try:
                kind = ScenarioKind(c.get("categoria", "feliz"))
            except ValueError:
                kind = ScenarioKind.feliz
            corpo = (
                f"# {c.get('nome', '')} (nível: {c.get('nivel', '')}; "
                f"RNs: {', '.join(c.get('rns', []))})\n{c.get('gherkin', '')}"
            )
            cen = TestScenario(story_id=story_id, kind=kind, gherkin=corpo)
            session.add(cen)
            session.flush()
            _audit(
                session,
                actor_id=actor.id,
                action="propor",
                entity="test_scenario",
                entity_id=cen.id,
                before=None,
                after={"story_id": story_id, "kind": kind, "nome": c.get("nome")},
                run_id=run_id,
            )
    session.commit()


def _cenarios_map(session: Session, run_id: int) -> dict[int, list[dict]]:
    """{story_id: [{kind, gherkin}]} dos cenários do run (E5)."""
    out: dict[int, list[dict]] = {}
    for cen in session.scalars(
        select(TestScenario)
        .join(Story)
        .join(Epic)
        .where(Epic.run_id == run_id)
        .order_by(TestScenario.id)
    ):
        out.setdefault(cen.story_id, []).append(
            {"kind": cen.kind, "gherkin": cen.gherkin}
        )
    return out


def persistir_fatias(
    session: Session,
    run_id: int,
    fatias: list[dict],
    historias: list[dict],
    base_dir: str | None = None,
) -> None:
    """Grava as fatias (slices) + o pacote F-XXX.md (banco + arquivo).

    Idempotente por run. O markdown fica em `slices.package_md` (fonte de
    verdade); o arquivo em `docs/fatias/F-XXX.md` é best-effort (pode não
    existir dentro do container, onde docs/ não é montado).
    """
    from .agents.fatiador import renderizar_pacote

    if session.scalar(select(Slice.id).where(Slice.run_id == run_id).limit(1)):
        return
    actor = default_user(session)
    historias_map = {h["id"]: h for h in historias}
    cenarios_map = _cenarios_map(session, run_id)

    for i, fatia in enumerate(fatias, start=1):
        code = f"F-{i:03d}"
        package_md = renderizar_pacote(code, fatia, historias_map, cenarios_map)
        path = f"docs/fatias/{code}.md"
        sl = Slice(
            run_id=run_id,
            code=code,
            title=fatia.get("nome", code)[:512],
            status=SliceStatus.planejada,
            package_path=path,
            package_md=package_md,
        )
        session.add(sl)
        session.flush()
        _audit(
            session,
            actor_id=actor.id,
            action="propor",
            entity="slice",
            entity_id=sl.id,
            before=None,
            after={"code": code, "historias": fatia.get("historia_ids", [])},
            run_id=run_id,
        )
        if base_dir:
            try:
                dest = Path(base_dir)
                dest.mkdir(parents=True, exist_ok=True)
                (dest / f"{code}.md").write_text(package_md, encoding="utf-8")
            except OSError:
                pass  # best-effort: o banco é a fonte de verdade
    session.commit()


def atualizar_status_fatia(
    session: Session, run_id: int, code: str, novo_status: str
) -> Slice | None:
    """Muda o status de uma fatia (planejada/em_dev/entregue), auditado."""
    sl = session.scalar(
        select(Slice).where(Slice.run_id == run_id, Slice.code == code)
    )
    if sl is None:
        return None
    try:
        status = SliceStatus(novo_status)
    except ValueError as e:
        raise ValueError(f"status inválido: {novo_status}") from e
    actor = default_user(session)
    antes = {"status": sl.status}
    sl.status = status
    _audit(
        session,
        actor_id=actor.id,
        action="status",
        entity="slice",
        entity_id=sl.id,
        before=antes,
        after={"status": sl.status},
        run_id=run_id,
    )
    session.commit()
    return sl


def aplicar_decisoes_historias(
    session: Session, run_id: int, decisoes: dict[str, str]
) -> None:
    """Aprova/rejeita histórias por id (US-xx casado pelo título? não — por id
    de banco em string). `decisoes`: str(story_id) -> 'aprovar' | 'rejeitar'.
    """
    actor = default_user(session)
    novo = {"aprovar": "aprovada", "rejeitar": "rejeitada"}
    for story in session.scalars(
        select(Story).join(Epic).where(Epic.run_id == run_id)
    ):
        acao = decisoes.get(str(story.id))
        if acao not in novo:
            continue
        antes = {"status": story.status}
        story.status = novo[acao]
        _audit(
            session,
            actor_id=actor.id,
            action=acao,
            entity="story",
            entity_id=story.id,
            before=antes,
            after={"status": story.status},
            run_id=run_id,
        )
    session.commit()
