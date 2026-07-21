# Kit SDLC Multiagente — implementação via Claude Code

Este kit transforma sua ideia em um repositório que o Claude Code consegue
construir de forma incremental e verificável. Ele contém:

| Arquivo | Papel |
|---|---|
| `CLAUDE.md` | Convenções que o Claude Code lê automaticamente em toda sessão |
| `docs/PRD.md` | A especificação do produto (o "o quê") |
| `docs/FASES.md` | Os prompts de implementação, fase a fase (o "como") |
| `instructions/*.md` | System prompts dos agentes DO PRODUTO (grill me, analista, etc.) |
| `.claude/commands/nova-fatia.md` | Slash command `/nova-fatia` para implementar cada fatia vertical |

## Como usar (5 passos)

1. **Crie o repositório** e copie todo o conteúdo deste kit para a raiz.
   ```bash
   git init forge-sdlc && cd forge-sdlc
   # copie os arquivos do kit aqui, depois:
   git add -A && git commit -m "chore: kit inicial de especificação"
   ```

2. **Abra o Claude Code** na raiz do repo. Ele lerá o `CLAUDE.md` sozinho.

3. **(Recomendado) Rode o "grill me" em você mesmo primeiro.** Antes de gerar
   código, cole no Claude Code:
   > Leia docs/PRD.md e instructions/grill_me.md. Assuma o papel do Grill Me
   > e me entreviste sobre lacunas do PRD (máx. 5 perguntas por rodada).
   > Ao final, atualize o PRD com minhas respostas.

   Isso valida a própria técnica que o produto usará — e melhora o PRD.

4. **Execute as fases em ordem.** Abra `docs/FASES.md` e cole o prompt da
   Fase 1. Só avance para a próxima fase quando os critérios de aceite da
   fase atual passarem (o prompt de cada fase exige isso explicitamente).
   Commit ao fim de cada fase.

5. **A partir da Fase 6**, cada funcionalidade vira uma fatia vertical
   implementada com `/nova-fatia docs/fatias/F-XXX.md` — front + API + banco
   + testes juntos, CI verde antes do merge. Nunca uma camada sozinha.

## Princípios do kit

- **Fases pequenas e verificáveis.** Claude Code rende muito mais com
  entregas incrementais testáveis do que com um mega-prompt.
- **Prompt é artefato versionado.** Os agentes do produto vivem em
  `instructions/*.md`; mudanças passam por PR como qualquer código.
- **Human-in-the-loop nos pontos certos.** Regras de negócio e histórias
  são aprovadas por você antes de alimentar as etapas seguintes.
- **Conteúdo importado é entrada não confiável.** Materiais enviados pelos
  usuários passam por guardrails antes de chegar aos agentes (injeção
  indireta é o risco nº 1 deste produto).
