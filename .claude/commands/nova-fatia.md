---
description: Implementa uma fatia vertical completa a partir de um pacote de fatia (docs/fatias/F-XXX.md)
---
Implemente a fatia vertical descrita em: $ARGUMENTS

Processo obrigatório:
1. Leia o pacote da fatia por inteiro e o CLAUDE.md. Liste em um TODO as
   histórias, endpoints, migrations, componentes de UI e cenários de teste.
2. Implemente na ordem: migration → API (com testes de integração) →
   UI consumindo a API real → testes e2e dos cenários marcados como e2e.
3. É PROIBIDO concluir com camada faltando: se o pacote não especificar
   alguma camada, pare e me pergunte antes de prosseguir.
4. Rode: lint, pytest, vitest e playwright. Corrija até tudo passar.
5. Confira cada item do Definition of Done do pacote, marcando o checklist
   no próprio arquivo da fatia.
6. Execute o Roteiro de demo do pacote e reporte o resultado passo a passo.
7. Commit em Conventional Commits referenciando a fatia (ex.:
   "feat(F-003): fatia de cadastro ponta a ponta").
