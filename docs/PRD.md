# PRD — Forge SDLC (v2)

> v2 incorpora as decisões da entrevista Grill Me de 2026-07-21 (4 rodadas).
> Mudanças principais: provider de LLM definido (DeepSeek V4), imutabilidade
> das regras de negócio, subgrafo de refino de RNs, trilha de auditoria e
> métrica de sucesso por bootstrap.

## 1. Visão
Times pequenos recebem descrições esparsas de sistemas (e-mails, atas, PDFs,
rascunhos) e perdem semanas transformando isso em backlog implementável. O
Forge SDLC ingere esses materiais, **entrevista o solicitante para fechar
lacunas** (Grill Me), e produz artefatos ágeis rastreáveis — regras de
negócio → histórias E2E → stack + cenários de teste → fatias verticais —
prontos para implementação com CI/CD a cada entrega.

**Visão de longo prazo (v2+, fora do escopo v1):** um pipeline capaz de
produzir a si mesmo e, a partir daí, sistemas inteiros com alta qualidade,
observabilidade, economia e segurança. A v1 prova o ciclo com humano no
loop na etapa de implementação; a automação de E7 é decisão futura.

## 2. Personas
- **PO/Analista** — importa materiais, responde o Grill Me, aprova regras e histórias.
- **QA** — revisa cenários de teste gerados por história.
- **Dev** — consome os "pacotes de fatia" e implementa (com Claude Code) cada fatia vertical.

Na v1 os três papéis são exercidos pelo mesmo operador (uso pessoal,
single-tenant). O modelo de dados já separa os papéis para permitir escala
sem migração destrutiva — ver §5 e §6.

## 3. Arquitetura

```
┌─────────────────────────────  docker compose  ─────────────────────────────┐
│                                                                            │
│  apps/web (Next.js)          apps/api (FastAPI + LangGraph)                │
│  ├ upload de materiais  ──▶  ├ /projects /materials /runs (REST)           │
│  ├ chat do Grill Me     ◀──▶ ├ Grafo do pipeline (LangGraph)               │
│  ├ board de regras/     ──▶  │   ingestão → grill_me ⇄ humano              │
│  │  histórias (aprovar)      │   → [extrator ⇄ crítico ⇄ refinador]        │
│  └ visão de fatias/runs      │   → analista_historias                      │
│                              │   → [arquiteto ∥ designer_testes]           │
│                              │   → fatiador → pacotes de fatia             │
│                              ├ src/llm.py → provider externo (DeepSeek)    │
│                              └ tools: parse_docs, rag_busca, ...           │
│                                                                            │
│  postgres + pgvector         langfuse (traces/custos/datasets)             │
└────────────────────────────────────────────────────────────────────────────┘
```

Agentes rodam no backend via LangGraph com checkpointer Postgres (o pipeline
pausa em pontos de aprovação humana e retoma dias depois, se preciso).

### 3.1 Camada de modelos (decidido na entrevista)

**Provider: DeepSeek V4**, consumido pelo **formato OpenAI**
(`https://api.deepseek.com`) via `langchain-openai`. Motivo: é o caminho mais
maduro dentro do LangGraph e o `CallbackHandler` do Langfuse funciona
nativamente por ele. A DeepSeek também expõe um endpoint em formato Anthropic
(`https://api.deepseek.com/anthropic`) — documentado como rota alternativa,
não como caminho principal.

**Abstração de provider.** Toda construção de cliente passa por um único
factory em `apps/api/src/llm.py`, parametrizado por env:
`LLM_BASE_URL`, `LLM_API_KEY`, `MODEL_<NÓ>`. Apontar o pipeline para OpenAI,
OpenRouter, Together ou um vLLM local é mudança de `.env`, não de código.
Nenhum módulo do `apps/api` importa SDK de provider específico diretamente.

**Roteamento por nó** (configurável em env, valores abaixo são o padrão):

| Nó                                   | Modelo               | Thinking |
| ------------------------------------ | -------------------- | -------- |
| grill_me, extrator_regras, critico_regras, analista_historias, arquiteto_stack, designer_testes | `deepseek-v4-pro`   | on       |
| consolidador de RNs, classificações, sumarizações | `deepseek-v4-flash` | off      |

Contexto de 1M tokens e saída de até 384K eliminam risco de truncamento —
o dossiê completo cabe no prompt sem chunking adicional.

**Saídas tipadas — blindagem em 3 camadas.** O provider **não oferece JSON
Schema estrito** (as features publicadas são `Json Output`, `Tool Calls`,
`Chat Prefix Completion` e `FIM Completion`). `json_object` garante JSON
válido, não aderência ao schema. Portanto, toda saída de agente passa por:

1. **Forced tool call**: uma tool única cujo `input_schema` é o schema
   Pydantic do nó, com `tool_choice` forçado. Caminho principal — o modelo
   preenche uma assinatura de função, o que é sensivelmente mais aderente
   que instrução textual. Fallback para `json_object` + schema injetado no
   prompt em nós simples ou onde a camada 1 não estiver disponível.
2. **Validação Pydantic** da saída.
3. Em `ValidationError`, **re-prompt automático** com o erro do Pydantic
   anexado (máx. 2 tentativas), depois falha o nó com erro explícito na UI.

Isso preserva a regra "saída tipada, nunca regex" independentemente do
provider, e continua válido se o provider passar a suportar JSON Schema
estrito (a camada 3 vira rede de segurança em vez de caminho principal).
`Chat Prefix Completion` fica disponível como recurso extra caso algum nó
precise forçar o início da saída.

> **Resolvido no spike da Fase 3 (2026-07-22):** confirmado empiricamente
> que **forced tool call conflita com o thinking mode** da DeepSeek
> (`400 "Thinking mode does not support this tool_choice"`), e que o
> `response_format` de JSON Schema estrito também não é aceito
> (`400 "This response_format type is unavailable now"`). Decisão: a
> `structured_call` usa **uniformemente** `response_format=json_object` +
> JSON Schema injetado no prompt + validação Pydantic + re-prompt (camadas
> 1-fallback/2/3), que funciona tanto nos nós `pro` (thinking on) quanto no
> `flash`. Implementado em `apps/api/src/llm.py`, validado contra a DeepSeek.

**Claude Code não é dependência de runtime.** Ele é a ferramenta com que o
Forge é desenvolvido (execução de `docs/FASES.md`, comando `/nova-fatia`) e a
ferramenta de implementação em E7. Nenhum código de produção importa SDK da
Anthropic.

## 4. Pipeline — estágios e contratos

Cada estágio tem entrada tipada, saída tipada (Pydantic) e ponto de
aprovação humana onde indicado. O estado do run é persistido a cada passo.

**E1 — Ingestão.** Upload de PDF/DOCX/MD/TXT e colagem de texto livre.
Parse → chunking → embeddings → pgvector, com metadados de origem
(arquivo, página). Saída: corpus consultável por `rag_busca`.
Limites duros: 25 MB e ~200 páginas por arquivo, 50 materiais por projeto,
1 run ativo por projeto. Acima do limite: rejeita no upload com erro claro
na UI — nunca trunca em silêncio.

**E2 — Grill Me (HITL, iterativo).** Agente lê o corpus, avalia cobertura
contra o checklist do `instructions/grill_me.md` e envia rodadas de até 5
perguntas ao PO pelo chat. Respostas voltam ao corpus. Encerra quando o
checklist atinge cobertura mínima ou o PO encerra. Saída: **Dossiê do
Sistema** (documento estruturado: propósito, atores, funcionalidades,
restrições, integrações, dados, NFRs).

**E3 — Extração e refino de regras de negócio (subgrafo).** A qualidade das
RNs é o gargalo de todo o resto do pipeline, então este estágio é um
subgrafo de refino, não um prompt único:

1. **Gerador** (`instructions/extrator_regras.md`) roda 3× em paralelo sobre
   corpus + dossiê (self-consistency). RNs presentes nas 3 execuções entram
   com confiança alta.
2. **Consolidador** deduplica e funde variantes da mesma regra.
3. **Crítico** (`instructions/critico_regras.md` — agente separado, prompt e
   rubrica próprios) avalia cada RN por rubrica fixa: tem fonte citada? é
   testável? é atômica? é regra de negócio ou requisito de UI disfarçado?
   contradiz outra RN?
4. **Refinador** reescreve apenas as RNs reprovadas e devolve ao crítico.

Máximo de **3 iterações**; ao final entrega o conjunto marcando pendências
não resolvidas. Cada RN é numerada `RN-001…` com fonte obrigatória
(material/página ou resposta `Q-XX` do grill).
➤ **Aprovação humana**: PO aprova/rejeita cada RN.

*Nota de projeto:* a auto-crítica dentro do prompt do gerador foi descartada
— o ganho de qualidade vem do crítico ser um agente separado com rubrica.

**E3.1 — Imutabilidade e correção de RNs.** Uma RN aprovada **nunca é
editada**. O modelo é append-only:
- Correções e detalhamentos entram como RNs novas (incremental).
- Uma RN aprovada que se revele **factualmente errada é tratada como
  defeito**: recebe `status: contestada` + `motivo`, o que reabre uma rodada
  dirigida do Grill Me apenas sobre aquela lacuna. A resolução emite uma RN
  nova com `supersedes: RN-XXX`; a original passa a `status: superseded` —
  preservada, nunca apagada.
- Artefatos derivados de uma RN superada são marcados `stale` e podem ser
  reprocessados por ação explícita do PO (nunca automaticamente).

**E4 — Analista de Histórias.** Converte RNs aprovadas em épicos e
histórias INVEST com critérios de aceite Gherkin, mantendo matriz de
rastreabilidade RN ↔ US. Valida o fluxo E2E: monta o mapa de jornada e
itera até não restar RN órfã nem lacuna de jornada. ➤ **Aprovação humana**.

**E5 — Par paralelo (ramos simultâneos no grafo).**
- *Arquiteto de Stack*: propõe stack para o sistema-alvo com justificativa
  em formato ADR (contexto, opções, decisão, consequências).
- *Designer de Testes*: para cada história aprovada, gera cenários BDD
  (felizes, alternativos, de erro) — os testes nascem junto com a
  funcionalidade, nunca depois.

**E6 — Fatiador Vertical.** Agrupa histórias em **fatias verticais**:
cada fatia atravessa UI + API + persistência + testes.
Regra invariável do produto: **não existe fatia só-API, só-front ou
só-banco**. Saída: um "pacote de fatia" por fatia
(`docs/fatias/F-XXX.md`): histórias incluídas, contrato de API proposto,
modelo de dados, cenários de teste, Definition of Done.

**E7 — Implementação assistida.** Os pacotes de fatia alimentam o
Claude Code (`/nova-fatia`). v1 NÃO implementa código de produção
autonomamente — gera os artefatos que tornam a implementação humana+agente
rápida e verificável. CI/CD roda a cada fatia entregue.

## 5. Modelo de dados (mínimo)
`projects` → `materials` (arquivos) → `chunks` (embeddings)
`runs` (execuções do pipeline, com estágio atual e estado do grafo)
`grill_sessions` / `grill_qa` (perguntas e respostas)
`business_rules` (RN, fonte, `status`: proposta/aprovada/rejeitada/contestada/superseded,
  `supersedes` → RN anterior, `approved_by`, `approved_at`)
`epics` / `stories` (INVEST + Gherkin, status, rastreabilidade RN↔US, flag `stale`)
`adrs`, `test_scenarios`, `slices` (fatias e seus pacotes)
`users` (id, email, `role` ∈ `po|qa|dev|admin`) — **um único usuário na v1**,
  sem tela de gestão; existe para que a checagem de permissão possa ser
  ligada no futuro sem migração destrutiva
`audit_log` (actor_id, action, entity, entity_id, before, after, ts, run_id)

## 6. Requisitos não-funcionais

**Observabilidade.** Todo run do pipeline gera um trace no Langfuse
(sessão = run_id); logs estruturados JSON (structlog) correlacionados por
`run_id`; métricas por estágio: latência, tokens, custo, nº de iterações do
Grill Me, nº de iterações do subgrafo de refino, % RNs aprovadas sem edição.
**Toda mutação de RN, história, ADR, cenário ou fatia grava em `audit_log`**
(quem, o quê, quando, valor antes, valor depois, run_id), correlacionada ao
trace pelo `run_id`. Registro de ações é requisito da v1; **checagem de
permissão por papel fica desligada na v1** (um só operador) e é ativada
quando houver mais de um usuário.

**Segurança.** Materiais importados = entrada não confiável: scanner
LLM Guard (PromptInjection, Secrets) na ingestão E nos retornos de
`rag_busca`; conteúdo sempre delimitado como dados no prompt. Aprovação
humana obrigatória em E3/E4 (o pipeline nunca "decide o sistema" sozinho).
Limites duros configuráveis via env: máx. iterações por estágio, timeout por
tool, `MAX_TOKENS_PER_RUN` e `MAX_USD_PER_RUN` — run que estoura o teto é
abortado com erro claro na UI. Autenticação simples na v1 (single-tenant,
token). Chave do provider (`LLM_API_KEY`) apenas em `.env`, nunca commitada.

**Boas práticas.** Saídas tipadas Pydantic com a blindagem de 3 camadas
(§3.1); prompts versionados em `instructions/`; testes em três camadas
(tools determinísticas via pytest/TDD / avaliação DeepEval sobre dataset de
PRDs-exemplo / E2E Playwright); Conventional Commits; CI obrigatório verde
para merge.

## 7. Fora de escopo (v1)
Multi-tenant/SSO; geração autônoma de código de produção; deploy do
sistema-alvo; integração Jira/Linear (v2: exportar histórias); tela de
gestão de usuários e checagem de permissão por papel.

**Ressalva de dados registrada.** Todo material importado é enviado para a
API da DeepSeek — um terceiro. Enquanto os materiais forem do próprio
operador, isso é irrelevante. No momento em que o Forge processar documentos
de clientes, isso vira questão contratual e de compliance (LGPD), e exige
revisão desta seção antes do uso.

## 8. Métricas de sucesso (critério de aceite da v1)

O teste de sucesso é o **bootstrap**: alimentar o Forge com o próprio
`docs/PRD.md` como material de entrada e deixá-lo rodar o pipeline completo.

| Métrica                                                        | Alvo    |
| -------------------------------------------------------------- | ------- |
| Cobertura das fases de `docs/FASES.md` pelas fatias geradas     | ≥ 80%   |
| RNs aprovadas sem edição (qualidade da extração)                | ≥ 70%   |
| RN órfã / história sem RN de origem (teste automatizado)        | 0       |
| Custo por run                                                   | ≤ `MAX_USD_PER_RUN` |

As três primeiras são medidas por `scripts/eval.py` (Fase 7) contra o
dataset no Langfuse. Teste unitário/TDD cobre o determinístico (tools,
matriz de rastreabilidade, validadores, schemas); a avaliação estatística
cobre a qualidade não-determinística das saídas de agente.

> **[PENDENTE]** Valor numérico de `MAX_USD_PER_RUN` não definido na
> entrevista. Sugestão a validar após o primeiro run real medido.

## 9. Status
_(atualizado pelo Claude Code ao fim de cada fase de docs/FASES.md)_
- [x] Fase 1 — Fundação _(CI verde no primeiro push — os 3 jobs passaram)_
- [x] Fase 2 — Ingestão _(upload→parse→chunk→embed→pgvector + rag_busca;
  fastembed/ONNX por ADR-001; validado end-to-end)_
- [x] Fase 3 — Grill Me _(subgrafo HITL com interrupt + PostgresSaver: resume
  após matar o container validado; UI de entrevista + dossiê; Langfuse ligado
  via CallbackHandler, session=run_id, no-op sem chaves. Dossiê e Q&A agora
  persistidos em domínio: `runs.dossie`, `grill_sessions`, `grill_qa` —
  não mais só no checkpointer; endpoints GET /runs/{id}/dossie e /grill)_
- [x] Fase 4 — Regras + Histórias _(E3: subgrafo extrator×3 paralelo →
  consolidador → crítico⇄refinador (máx. 3) → interrupt de aprovação; RN
  imutável por trigger no banco. E3.1: contestar → rodada dirigida do Grill
  Me → RN nova com `supersedes` (append-only), original `superseded` e
  histórias derivadas `stale`. E4: analista com loop de matriz RN↔US
  (sem órfãs). Boards de RN e histórias na UI. 31 testes verdes, incl.
  imutabilidade, matriz de rastreio e supersede)_
- [x] Fase 5 — Arquiteto ∥ Testes _(E5: dois ramos PARALELOS no grafo
  (arquiteto de stack → ADR ∥ designer de testes → cenários BDD por história),
  fan-in → persistir. ≥3 cenários/história (feliz/alternativo/erro);
  cenário órfão impossível (FK NOT NULL). UI: ADR + cenários por história.
  36 testes verdes)_
- [ ] Fase 6 — Fatiador + /nova-fatia
- [ ] Fase 7 — Observabilidade completa
- [ ] Fase 8 — Segurança + hardening
