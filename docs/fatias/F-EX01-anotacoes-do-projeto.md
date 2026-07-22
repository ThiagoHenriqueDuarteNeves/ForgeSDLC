# F-EX01 — Anotações do projeto

> Fatia-exemplo do estágio **E7** (implementação assistida via `/nova-fatia`).
> Gerada no formato do Fatiador (E6) a partir de um mini-PRD fictício, para
> comprovar que o pacote basta para implementar a fatia ponta a ponta, sem
> abrir outros documentos, e que a entrega passa no CI (PRD Fase 6/E7).

Mini-PRD (material fictício de teste): _"No painel do projeto, quero anotar
lembretes livres (ex.: 'faltou o material de compliance') e ver a lista, para
registrar contexto sem sair da tela."_

## Histórias incluídas
### [id=1] Registrar uma anotação no projeto
RNs: RN-EX1 (a anotação pertence a um projeto existente e não é vazia)
```gherkin
Funcionalidade: Anotações do projeto
  Cenário: adicionar uma anotação
    Dado um projeto existente
    Quando eu envio o texto "faltou o material de compliance"
    Então a anotação é salva e passa a aparecer na lista do projeto
```

### [id=2] Listar as anotações do projeto (mais recentes primeiro)
RNs: RN-EX2 (a lista traz só as anotações do próprio projeto, da mais nova à mais antiga)
```gherkin
  Cenário: listar anotações
    Dado um projeto com duas anotações
    Quando eu abro o painel de anotações
    Então vejo as duas, a mais recente no topo
```

## Contrato de API proposto
- `POST /projects/{project_id}/notes` — body `{ "text": "..." }` →
  `201 { id, text, created_at }`. `422` se `text` vazio; `404` se o projeto não existe.
- `GET /projects/{project_id}/notes` → `200 [{ id, text, created_at }]`
  ordenado por `id` desc (mais recentes primeiro). `404` se o projeto não existe.

## Modelo de dados
Tabela `project_notes`:
- `id` PK
- `project_id` FK → `projects.id`
- `text` TEXT (não vazio)
- `created_at` timestamptz default now()

Migration Alembic versionada, encadeada na cabeça atual.

## UI
Painel **"Anotações"** no painel do projeto (`ProjectPanel`): campo de texto +
botão "Anotar" (POST na API real) e a lista abaixo (GET), atualizando após
salvar. Trata erro (banner) e estado de envio. Sem mock — consome a API real.

## Cenários de teste (do designer de testes)
- [feliz] POST com texto válido cria a anotação e ela aparece no GET (pytest, integração).
- [alternativo] GET de um projeto sem anotações retorna lista vazia (pytest).
- [erro] POST com texto vazio é rejeitado com 422 (pytest).
- [erro] POST/GET em projeto inexistente retorna 404 (pytest).
- [unit] cliente `criarNota`/`listarNotas` chama os endpoints certos (vitest).

## Definition of Done
- [x] UI consome a API real (sem mock) e trata erro/loading
- [x] API persiste e lê do banco via migration versionada
- [x] Todos os cenários desta fatia implementados e passando
- [x] Lint + CI verdes; trace da feature visível na observabilidade
- [x] Demonstrável: roteiro de demo em 5 passos incluído abaixo

## Roteiro de demo
1. Suba o stack (`docker compose up -d`) e abra a web.
2. Crie/abra um projeto no painel de Projetos.
3. No painel "Anotações", digite "faltou o material de compliance" e clique "Anotar".
4. Veja a anotação aparecer no topo da lista (veio do GET na API real).
5. Adicione uma segunda anotação e confirme a ordem (mais recente primeiro).
