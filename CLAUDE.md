# Forge SDLC — contexto para o Claude Code

## O que é este projeto
Pipeline multiagente que cobre o SDLC ágil: importa descrições esparsas de um
sistema, extrai regras de negócio via entrevista ("Grill Me"), gera histórias
de usuário end-to-end, escolhe stack e cenários de teste em paralelo, e fatia
o desenvolvimento em fatias verticais (UI + API + banco + testes, sempre juntos).
Especificação completa: `docs/PRD.md`. Plano de implementação: `docs/FASES.md`.

## Arquitetura (fixa — não alterar sem ADR)
- `apps/web`     → Next.js 14+ (App Router, TypeScript) — UI do pipeline
- `apps/api`     → Python 3.11 + FastAPI + LangGraph — orquestração dos agentes
- `instructions/`→ system prompts dos agentes, em Markdown (NUNCA hardcodar prompt em código)
- Postgres 16 + pgvector — dados do pipeline + embeddings dos materiais
- Langfuse (self-hosted) — traces de toda execução de agente
- DeepSeek V4 (formato OpenAI, via `langchain-openai`) — provider de LLM.
  Cliente construído SOMENTE pelo factory `apps/api/src/llm.py`, parametrizado
  por env (`LLM_BASE_URL`, `LLM_API_KEY`, `MODEL_<NÓ>`). Nenhum módulo importa
  SDK de provider direto. Modelos: `deepseek-v4-pro` (nós de raciocínio),
  `deepseek-v4-flash` (tarefas mecânicas). Ver PRD §3.1.
- Tudo sobe com `docker compose up` na raiz

## Convenções obrigatórias
- Prompts dos agentes: somente em `instructions/*.md`, carregados via
  `load_instructions()`. Mudança de prompt = mudança de comportamento = PR.
- Toda tool em `apps/api/src/tools/` tem docstring completa (o LLM a lê) e
  teste determinístico em `apps/api/tests/`.
- Toda chamada de agente recebe o callback do Langfuse. Código sem trace
  não entra.
- Conteúdo vindo de upload/import é NÃO CONFIÁVEL: passa por scanner
  (LLM Guard) e é delimitado como dados (`<material>...</material>`) antes
  de entrar em qualquer prompt.
- Saídas de agente que alimentam o pipeline são Pydantic tipado, nunca texto
  livre parseado com regex. O provider NÃO tem JSON Schema estrito — use a
  blindagem de 3 camadas do PRD §3.1: forced tool call com o schema como
  `input_schema` (fallback `json_object`) → validação Pydantic → re-prompt
  com o erro anexado, máx. 2 tentativas. Nunca `response_format=<schema>`.
- Regra de negócio aprovada é IMUTÁVEL. Correção entra como RN nova com
  `supersedes`; RN errada vira `status: contestada` e reabre o Grill Me.
  Nenhum código pode fazer UPDATE no texto de uma RN aprovada. Ver PRD §4/E3.1.
- Toda mutação de RN, história, ADR, cenário ou fatia grava em `audit_log`
  (actor, action, entity, before, after, ts, run_id). Sem log, não entra.
- Fatia vertical: uma entrega só está pronta quando UI consome a API, a API
  persiste no banco, testes (pytest + vitest/playwright) passam e o CI está
  verde. Não existem entregas "só backend" ou "só front".

## Comandos
- Subir tudo:            `docker compose up -d`
- API dev:               `cd apps/api && uvicorn src.main:app --reload`
- Web dev:               `cd apps/web && npm run dev`
- Testes backend:        `cd apps/api && pytest -q`
- Testes web:            `cd apps/web && npm test`
- E2E:                   `cd apps/web && npx playwright test`
- Lint:                  `ruff check apps/api && cd apps/web && npm run lint`

## Regras de trabalho
- Antes de considerar QUALQUER tarefa concluída: rode lint + testes.
- Commits: Conventional Commits (`feat:`, `fix:`, `test:`, `docs:`, `chore:`).
- Nunca commitar `.env`; manter `.env.example` atualizado.
- Ao terminar uma fase de `docs/FASES.md`, atualize a seção "Status" do PRD.
