# Guia Prático de Revisão de Pull Requests

> Checklist do Auto Shop System. Fonte normativa principal: `DEVELOPMENT_GUIDELINES.md`.  
> Use o diff, os testes e o comportamento esperado como evidência; código legado não é precedente automático.

## 1. Contexto e escopo

- [ ] O PR explica problema, solução, risco e forma de validação.
- [ ] O diff resolve o objetivo declarado e não mistura refatorações sem relação.
- [ ] Mudanças em `src/`, migration, API, frontend, testes e documentação estão rastreáveis entre si.
- [ ] O tamanho permite revisão confiável; se não, há justificativa ou divisão possível.
- [ ] Commits de correção não escondem mudança de requisito ou comportamento.

## 2. Arquitetura e dependências

- [ ] Imports continuam apontando para dentro: `api/infrastructure → application → domain`.
- [ ] `src/domain/` não importa FastAPI, Pydantic, SQLAlchemy, `api`, `application` ou `infrastructure`.
- [ ] `src/application/` não importa FastAPI, SQLAlchemy, `api` ou adapters concretos.
- [ ] Routes chamam casos de uso; não chamam repositories ou executam queries.
- [ ] Composição concreta permanece em `src/api/composition/` ou no bootstrap.
- [ ] `test_architecture_boundaries.py` foi atualizado se surgiu uma nova fronteira.

## 3. Domain

- [ ] A regra está na entidade, VO ou domain service correto, não em route/schema/repository/ORM.
- [ ] Criação e mutação preservam invariantes e bloqueiam transições inválidas.
- [ ] Filhos do agregado são alterados pelo aggregate root.
- [ ] VOs são imutáveis e válidos desde a construção.
- [ ] Dinheiro novo usa `Decimal`/`Money`, não `float`.
- [ ] Domain errors não conhecem HTTP ou infraestrutura.

## 4. Application e use cases

- [ ] O caso de uso expressa uma intenção clara e uma fronteira transacional.
- [ ] Dependências externas chegam por ports e constructor injection.
- [ ] Inputs/outputs são tipos internos explícitos, sem HTTP, ORM ou `dict[str, Any]`.
- [ ] O caso de uso orquestra o domínio sem duplicar invariantes.
- [ ] Uma nova classe `*Service` não acumula operações ou motivos de mudança sem relação.
- [ ] Efeitos externos são idempotentes/reprocessáveis e não precedem commit de forma insegura.

## 5. Ports e adapters

- [ ] O novo port protege um limite real; não existe apenas por cerimônia ou para facilitar mock.
- [ ] O contrato define ausência, errors, ordenação, paginação e efeitos transacionais.
- [ ] O port é pequeno e orientado ao consumidor; não é um Generic Repository universal.
- [ ] O adapter traduz domínio ↔ formato externo e não contém regra de negócio.
- [ ] ORM, `Row`, `Query` e `httpx.Response` não atravessam para o núcleo.
- [ ] Timeout/retry está definido; retry só ocorre em operação segura ou idempotente.

## 6. FastAPI

- [ ] A route apenas valida transporte, autentica, delega e mapeia a resposta.
- [ ] Request/response schemas estão no contexto correto e possuem limites explícitos.
- [ ] `response_model`, status code e método HTTP refletem o contrato (`GET` não muta).
- [ ] `Depends` permanece em API/composição.
- [ ] A route administrativa exige autenticação e autorização adequadas.
- [ ] Domain/application errors são traduzidos pelo handler central, sem `try/except` repetitivo.
- [ ] DTO público não expõe token, hash, PII ou campo interno.

## 7. PostgreSQL e persistência

- [ ] Repository usa `flush()`; o Unit of Work controla commit/rollback.
- [ ] Operações relacionadas e invariantes multi-write são atômicas.
- [ ] Models ORM e migration concordam em tipo, nulabilidade, default, FK, constraint e índice.
- [ ] `NOT NULL`, `UNIQUE`, FK e `CHECK` protegem invariantes importantes também no banco.
- [ ] Não há N+1, query em loop, lista ilimitada ou lazy loading fora da sessão.
- [ ] Mutação concorrente declara estratégia: SQL condicional, versão otimista ou lock.
- [ ] Aprovação, reserva, recebimento e retirada são idempotentes e não permitem lost update.

## 8. Nomenclatura

- [ ] Arquivos/funções/variáveis usam `snake_case`; classes `PascalCase`; constantes `UPPER_SNAKE_CASE`.
- [ ] Identificadores usam inglês e o vocabulário do domínio.
- [ ] Nomes revelam intenção; `process`, `manage`, `data`, `utils` ou `helpers` estão contextualizados.
- [ ] Ports usam `...Repository`/capacidade; adapters SQLAlchemy usam `SqlAlchemy...`.
- [ ] `Request/Response` ficam na API; `Command/Query/Result` na aplicação.

## 9. Clean Code

- [ ] Funções têm responsabilidade, nível de abstração e efeitos claros.
- [ ] Flags booleanas não selecionam casos de uso diferentes.
- [ ] Guard clauses reduzem aninhamento; condições de negócio complexas têm nomes.
- [ ] Comentários explicam decisões, não repetem código.
- [ ] Não há duplicação da mesma regra nem abstração criada só por semelhança visual.
- [ ] Tamanho de arquivo/função é tratado como sinal, não como critério isolado.

## 10. SOLID

- [ ] **SRP:** classe/módulo possui motivo coeso para mudar.
- [ ] **OCP:** nova variação implementa port/política sem condicionais espalhadas.
- [ ] **LSP:** adapter/fake preserva a semântica completa do contrato.
- [ ] **ISP:** consumidor não depende de métodos que não usa.
- [ ] **DIP:** use case depende do contrato interno, nunca da implementação concreta.
- [ ] A solução não adiciona patterns complexos apenas para “cumprir SOLID”.

## 11. Tipagem

- [ ] Parâmetros e retornos relevantes possuem tipos precisos.
- [ ] `X | None` representa ausência real; collections estão parametrizadas.
- [ ] Estruturas conhecidas usam dataclass, `TypedDict` ou DTO, não `Any`.
- [ ] `cast()`/`# type: ignore` possui causa legítima e escopo mínimo.
- [ ] Implementações de `Protocol` mantêm assinaturas e semântica compatíveis.

## 12. Tratamento de erros

- [ ] Error nasce na camada correta e chega à API por tradução central.
- [ ] Não existe `HTTPException` em domain/application.
- [ ] Falha externa indisponível não é confundida com input inválido.
- [ ] Exceções não são ignoradas e preservam causa com `raise ... from exc`.
- [ ] Resposta não vaza stack, SQL, URL sensível ou mensagem do driver.
- [ ] Rollback é garantido em falha transacional.

## 13. Dependency Injection

- [ ] Repositories, gateways, relógios, IDs e tokens são injetados quando afetam comportamento.
- [ ] Use case não instancia adapter concreto.
- [ ] Adapters da mesma transação compartilham sessão/UoW.
- [ ] Não há Service Locator, dependência global mutável ou `Depends` no núcleo.

## 14. Testes

- [ ] O PR adiciona testes para regra, caminho feliz, limites e errors alterados.
- [ ] Testes verificam comportamento, não detalhes internos irrelevantes.
- [ ] Domínio/aplicação usam fakes dos ports, sem banco/rede.
- [ ] Persistência/migration usa PostgreSQL real migrado; SQLite não é a única evidência.
- [ ] API testa status, schema, auth, autorização e formato de error.
- [ ] Regressão possui teste que falha sem a correção.
- [ ] Cobertura global permanece ≥80% com branches; áreas críticas estão plenamente exercitadas.

## 15. Segurança

- [ ] Inputs, path/query params, paginação e payloads possuem limites.
- [ ] Acesso administrativo aplica autenticação e autorização deny-by-default.
- [ ] Usuário não acessa recurso de outro cliente por troca de ID/token.
- [ ] Secrets, CPF/CNPJ, tokens e URLs sensíveis não aparecem em código, resposta ou log.
- [ ] Queries são parametrizadas; não existe mass assignment de campos protegidos.
- [ ] Endpoint público considera expiração, uso único, rate limit e enumeração.
- [ ] Nova dependência passou por análise de vulnerabilidades/licença.

## 16. Performance

- [ ] Não há query/chamada externa repetida em loop.
- [ ] Relacionamentos usam eager loading/projection quando necessário.
- [ ] Listas grandes são paginadas e ordenadas de forma estável.
- [ ] Código `async` não executa I/O bloqueante no event loop.
- [ ] Otimização adicionada responde a risco/medição real, não especulação.

## 17. Migrations

- [ ] Toda alteração de schema possui migration Alembic correspondente.
- [ ] Migration funciona em banco vazio e em upgrade com dados existentes.
- [ ] Nova coluna obrigatória possui estratégia segura de backfill.
- [ ] Lock, duração, reversão e compatibilidade durante deploy foram avaliados.
- [ ] Mudança destrutiva segue expandir → migrar → trocar → contrair.
- [ ] `alembic check` e contrato metadata/schema passam; downgrade não usa `pass` silencioso.

## 18. Novas dependências

- [ ] Não existe solução equivalente no projeto ou biblioteca padrão.
- [ ] A dependência resolve problema proporcional ao custo.
- [ ] Versão está fixada/gerenciada e o projeto está mantido.
- [ ] Licença, CVEs, tamanho, transitivas e superfície operacional foram avaliados.
- [ ] O adapter impede que a biblioteca vaze para domain/application.

## 19. Red flags

Investigue imediatamente: FastAPI/ORM em `domain`; `HTTPException` em `application`; repository concreto dentro de use case; regra em route/model ORM; `GenericRepository`; novo `utils/helpers`; novo `Any`/cast; query em loop; `commit()` em repository; token/PII em log; `Float` monetário; migration com `pass`; abstração de uso único; classe `Service` crescente; regra já existente duplicada.

## 20. Perguntas de julgamento

- Essa responsabilidade está na camada e no módulo corretos?
- A abstração resolve um limite real ou apenas aumenta indireção?
- Já existe solução equivalente no projeto?
- O caso de borda, concorrência ou falha parcial foi considerado?
- A mudança quebra contrato, dado existente ou outro fluxo?
- A solução é fácil de testar, operar e remover?
- O diff copia uma dívida atual em vez do padrão do `DEVELOPMENT_GUIDELINES.md`?

## 21. Classificação de comentários

- **Blocking:** precisa ser resolvido antes do merge. Ex.: “Blocking: a route grava no banco sem UoW.”
- **Suggestion:** melhoria recomendada não bloqueante. Ex.: “Suggestion: nomear a condição para melhorar a leitura.”
- **Question:** esclarecimento necessário. Ex.: “Question: como duas aprovações concorrentes são tratadas?”
- **Nitpick:** detalhe opcional de estilo. Ex.: “Nitpick: este nome pode ser mais específico.”

Todo comentário deve explicar risco, evidência no diff e, quando útil, direção de correção. Não marque preferência pessoal como Blocking.

## 22. Checklist final

- [ ] Objetivo e diff completo foram compreendidos.
- [ ] Arquitetura, domínio e contratos foram respeitados.
- [ ] Errors, transação, concorrência e banco foram avaliados.
- [ ] Testes demonstram comportamento e reduzem risco de regressão.
- [ ] Segurança, exposição de dados e performance foram consideradas.
- [ ] CI/gates aplicáveis passaram e documentação foi atualizada.
- [ ] Perguntas foram respondidas e não resta comentário **Blocking**.
