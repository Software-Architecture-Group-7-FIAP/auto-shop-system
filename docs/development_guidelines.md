# Diretrizes Oficiais de Desenvolvimento

> Referência normativa para evolução do Auto Shop System.  
> Versão 1.1 — 23/07/2026  
> Escopo principal: Python 3.12, FastAPI, PostgreSQL, SQLAlchemy e Alembic.

## 0. Como usar este documento

Este guia prescreve como código novo deve ser projetado, implementado e testado. O código atual foi analisado como evidência, não como padrão automaticamente correto.

- **MUST**: regra obrigatória; exceções exigem justificativa arquitetural registrada no PR ou ADR.
- **SHOULD**: recomendação forte; desvios devem ser conscientes e justificados.
- **MAY**: opção válida conforme o contexto.

Requisitos, segurança, integridade de dados e ADRs aprovados prevalecem sobre preferências de estilo.

### Estado atual resumido

O backend é um monólito modular com DDD-light e Ports and Adapters:

```text
src/
├── domain/          # entidades, Value Objects, regras e repository ports
├── application/     # casos de uso/application services e ports
├── infrastructure/  # SQLAlchemy, PostgreSQL, JWT, SMTP, PDF e APIs externas
├── api/             # FastAPI, schemas, mappers, routers e composição
├── config.py
└── main.py
```

Módulos funcionais: `auth`, `customer`, `vehicle`, `supplier`, `product`, `service_catalog`, `budget`, `service_order`, `inventory`, `execution` e `billing`. São candidatos a bounded contexts, mas ainda compartilham banco, enums e dependências de domínio.

## 1. Princípios fundamentais

1. **Dependências para dentro.** Camadas externas dependem das internas, nunca o contrário.
2. **Simplicidade.** Prefira a solução mais simples que preserve regras, segurança e limites.
3. **Alta coesão e baixo acoplamento.** Agrupe código pelo mesmo motivo de mudança.
4. **Responsabilidades separadas.** Negócio, orquestração, transporte e I/O não se misturam.
5. **Dependências explícitas.** Recursos externos são recebidos por construtor ou parâmetro.
6. **Testabilidade.** Domínio deve rodar sem HTTP ou banco; aplicação usa fakes dos ports.
7. **Invariantes próximas dos dados.** Entidades protegem seus próprios estados válidos.
8. **Abstrações proporcionais.** Não crie interfaces ou patterns por cerimônia.
9. **Código explícito.** Evite generics, herança e metaprogramação que prejudiquem a leitura.
10. **Evolução incremental.** Mudanças pequenas e verificáveis são preferíveis a big bang.

Duplicação da mesma regra deve ser removida. Semelhança visual isolada não justifica uma abstração: duplicação local pode ser mais barata que a abstração errada.

## 2. Arquitetura Hexagonal

### Camadas

| Camada | Responsabilidade | Não pode conter |
|---|---|---|
| `domain` | entidades, agregados, VOs, enums, invariantes, domain services e errors | FastAPI, Pydantic, SQLAlchemy, HTTP, sessão ou I/O |
| `application` | casos de uso, Commands, Queries, outputs, ports e transações | `Depends`, ORM, queries, adapters concretos ou respostas HTTP |
| `infrastructure` | persistência, JWT, SMTP, PDF, APIs externas e mappers ORM | regras de negócio ou decisões HTTP |
| `api` | routers, schemas, mappers, auth HTTP, handlers e composição | regras de negócio, queries em routes ou ORM como contrato |

### Fluxo de execução

```text
HTTP → FastAPI route → use case → domain
                              ↓
                       repository port
                              ↓
                  adapter SQLAlchemy → PostgreSQL
```

O use case chama domínio e ports; entidades nunca chamam repositories.

### Regras

- **MUST** manter `domain` livre de frameworks e camadas externas.
- **MUST** manter `application` livre de `api` e `infrastructure`.
- **MUST** impedir controllers de chamar repositories diretamente.
- **MUST** manter composition roots em `src/api/composition/` ou no bootstrap.
- **SHOULD** manter repository ports junto ao agregado e gateways tecnológicos em `application/ports`.
- **MAY** usar read models específicos para consultas complexas.
- **MUST NOT** introduzir CQRS, Event Sourcing, mensageria ou microserviços sem necessidade demonstrável e ADR.
- **MUST** preservar e ampliar `tests/unit/test_architecture_boundaries.py`.

## 3. Domain

### Entidades e agregados

- **MUST** colocar invariantes no método que cria ou altera estado.
- **MUST** modelar transições válidas e bloquear estados terminais/inválidos.
- **MUST** evitar setters genéricos para atributos protegidos por regra.
- **MUST** modificar filhos pelo aggregate root quando fazem parte da mesma consistência.
- **SHOULD** expor coleções defensivamente.
- **MAY** usar mutação controlada dentro do agregado; efeitos inesperados são proibidos.
- **SHOULD** usar `@dataclass` quando simplificar sem criar modelo anêmico.

Exemplo: `Budget.approve()` deve validar o estado anterior e realizar a transição; nunca altere `budget.status` diretamente.

### Value Objects e domain services

- **SHOULD** criar VO quando validação, normalização, unidade ou igualdade por valor forem recorrentes e relevantes.
- **MUST** tornar VOs imutáveis e válidos desde a construção.
- **SHOULD** manter `Document` e `Plate` como referências do padrão atual.
- **MUST** usar `Decimal`/`Money` para novos valores monetários, nunca `float`.
- **SHOULD** usar função/domain service puro quando uma regra não pertencer naturalmente a uma entidade.
- **MUST NOT** realizar I/O em domain services.

### Erros de domínio

- **MUST** derivar erros de uma hierarquia interna como `DomainError`.
- **MUST** nomear a violação de negócio, não o status HTTP.
- **MUST** manter mensagens seguras e sem detalhes técnicos.
- **SHOULD** usar subclasses específicas quando consumidores precisarem distinguir o erro.

## 4. Application e casos de uso

Cada caso de uso representa uma intenção: `CreateCustomer`, `ApproveBudget`, `AssignMechanic`, `CreateInvoice`.

- **MUST** ter responsabilidade e fronteira transacional claras.
- **MUST** receber recursos externos por ports.
- **MUST** orquestrar o domínio, sem duplicar invariantes.
- **MUST** retornar domínio ou outputs próprios, nunca `Response`, `HTTPException`, ORM ou sessão.
- **SHOULD** usar `@dataclass(frozen=True, slots=True)` em Commands, Queries e outputs.
- **MUST NOT** usar `dict[str, Any]` quando a estrutura for conhecida.
- **SHOULD** dividir classes `*Service` quando acumularem casos de uso ou razões para mudar.
- **MAY** manter services pequenos e coesos; não é obrigatório criar uma classe por endpoint.

Exemplo: `ApproveBudgetCommand` contém o `budget_id`; `ApprovedBudget` retorna os IDs do orçamento e da OS, sem objetos HTTP ou ORM.

### Transações e efeitos

- **MUST** controlar a transação no caso de uso, nunca no repository ou route.
- **MUST** fazer o Unit of Work garantir rollback automático sem commit ou em exceção.
- **MUST** manter operações que exigem consistência na mesma transação.
- **MUST** definir idempotência para operações repetíveis.
- **SHOULD** confirmar persistência antes de SMTP/API externa e tornar o efeito reprocessável.
- **SHOULD** usar outbox quando banco e notificação precisarem de entrega confiável.

## 5. Ports

Port representa uma capacidade necessária ao núcleo, não uma tecnologia.

Crie um port quando houver I/O, limite arquitetural, política variável, implementação substituível ou fake significativo. Não crie para função pura, por formalidade ou apenas para “mockar tudo”.

- **SHOULD** usar `typing.Protocol` como padrão, conforme o projeto atual.
- **MAY** usar `ABC` quando houver comportamento compartilhado ou necessidade nominal real.
- **MUST** manter contratos pequenos e orientados ao consumidor.
- **MUST** documentar ausência, erros, ordenação, paginação e efeitos transacionais.
- **MUST NOT** permitir commit oculto em implementação.
- **SHOULD** ter repository por agregado/finalidade, não `GenericRepository[T]` universal.
- **SHOULD** segregar leitura e escrita quando as necessidades forem diferentes.

## 6. Adapters

### Entrada

Routes, CLI e futuros consumers devem validar transporte, autenticar, chamar um caso de uso e traduzir resposta/erro. Não contêm regra ou query.

### Saída

- **MUST** implementar port interno.
- **MUST** traduzir modelo externo para domínio/output interno.
- **MUST** encapsular biblioteca, timeout e detalhes do provedor.
- **SHOULD** aplicar retry somente a operação segura/idempotente, com limite e backoff.
- **MUST NOT** retornar `Row`, `Query`, `httpx.Response` ou ORM ao núcleo.
- **SHOULD** usar mappers explícitos `_to_domain`/`_to_model`.
- **MUST** carregar o necessário para preservar invariantes e evitar lazy loading fora da sessão.

## 7. FastAPI

- **MUST** usar `APIRouter` e schemas por contexto.
- **MUST** manter routes finas: validar, resolver dependências, executar e mapear.
- **MUST** declarar `response_model` para respostas estruturadas.
- **MUST** usar `POST`, `PUT`, `PATCH` ou `DELETE` para mutações; `GET` é seguro.
- **MUST** usar `201` em criação e `204` quando remoção não retornar body.
- **MAY** usar `200` com representação ou `202` para processamento assíncrono.
- **SHOULD** usar `def` com SQLAlchemy síncrono; `async def` somente com I/O awaitable.
- **MUST** manter schemas Pydantic na API e invariantes no domínio.
- **MUST** usar DTO público reduzido e nunca expor hashes, tokens ou PII desnecessária.
- **SHOULD** dividir o atual `src/api/schemas.py` por módulo ao tocá-lo.
- **MUST** centralizar tradução de errors em exception handlers.
- **MUST NOT** repetir `try/except DomainError` em cada route.

### Auth e paginação

- **MUST** proteger routes administrativas e autorizar ações por policy/RBAC.
- **MUST** validar algoritmo, assinatura, expiração e claims do JWT.
- **MUST** limitar login por IP/identidade sem revelar se usuário existe.
- **MUST** usar token público expirável, de uso único e persistido por fingerprint.
- **MUST** configurar CORS por allowlist e nunca logar token ou PII.
- **MUST** limitar paginação e definir ordenação estável.
- **SHOULD** retornar `items`, `total`, `limit` e `offset` quando o cliente precisar navegar.

## 8. PostgreSQL e persistência

### Models e integridade

- **MUST** tratar SQLAlchemy models como persistência, não domínio.
- **MUST** manter tipo, nulabilidade, default, constraint, índice e FK equivalentes no ORM e Alembic.
- **MUST** distinguir default Python de `server_default`.
- **MUST** usar `Numeric`/`Decimal` ou minor units para dinheiro.
- **MUST** usar timestamps timezone-aware em UTC.
- **MUST** declarar `CASCADE`, `RESTRICT` ou `SET NULL` deliberadamente.
- **MUST** proteger invariantes com `NOT NULL`, `UNIQUE`, FK e `CHECK` quando expressáveis.
- **MUST** traduzir `IntegrityError`; mensagens do driver não chegam à API.
- **MUST** deixar `commit()` para o Unit of Work; repositories usam `flush()`.

### Queries e concorrência

- **MUST** evitar N+1 e queries dentro de loops; use eager loading, batch ou agregação.
- **MUST** paginar listas potencialmente grandes.
- **SHOULD** selecionar apenas colunas necessárias em read models.
- **MUST** justificar índices pela constraint ou consulta atendida.
- **MUST** definir estratégia para mutação concorrente: SQL condicional, versão otimista ou lock.
- **MUST** garantir idempotência com chave/constraint em aprovação, reserva, recebimento e retirada.
- **MUST** impedir saldo negativo e lost update no estoque.
- **SHOULD** testar concorrência com sessões PostgreSQL reais.

### Migrations

- **MUST** usar Alembic para toda mudança de schema fora de testes.
- **MUST** testar banco vazio e upgrade de versão suportada em PostgreSQL.
- **MUST** executar `alembic check` e teste de contrato metadata/schema.
- **MUST** fazer mudanças destrutivas em fases: expandir, migrar, trocar e contrair.
- **MUST** usar downgrade real/testado ou declarar migration forward-only; `pass` silencioso é proibido.
- **MUST NOT** usar `Base.metadata.create_all()` em implantação.

## 9. Nomenclatura

| Elemento | Padrão | Exemplo |
|---|---|---|
| arquivos/packages | `snake_case` | `service_order` |
| classes/errors | `PascalCase` | `BudgetRepository` |
| funções/variáveis | `snake_case` | `create_customer` |
| constantes | `UPPER_SNAKE_CASE` | `MAX_PAGE_SIZE` |
| booleanos | condição clara | `is_active`, `can_edit` |

- **MUST** usar inglês nos identificadores e português em mensagens ao usuário.
- **MUST** preservar o vocabulário do domínio.
- **SHOULD** usar verbos claros: `create`, `find`, `calculate`, `validate`.
- **SHOULD** evitar `process`, `manage`, `data`, `utils` quando houver nome específico.
- **MUST** usar `SqlAlchemy...Repository` para adapter concreto e `...Repository` para port.
- **SHOULD** reservar `Request/Response` para API e `Command/Query/Result` para aplicação.

## 10. Clean Code

- **MUST** manter funções focadas, nomeadas pela intenção e com efeitos explícitos.
- **SHOULD** usar poucos argumentos e agrupar parâmetros que formam conceito.
- **SHOULD** usar guard clauses e early returns.
- **MUST NOT** usar flag booleana para executar casos de uso diferentes.
- **SHOULD** separar cálculo puro de I/O.
- **MUST NOT** impor limite arbitrário de linhas; avalie coesão, complexidade e motivos para mudar.
- **SHOULD** comentar decisões, restrições e motivos não evidentes.
- **MUST NOT** comentar o óbvio ou manter código comentado.
- **MUST** evitar estado global mutável.
- **SHOULD** preferir composição a herança.

## 11. SOLID

| Princípio | Aplicação no projeto |
|---|---|
| SRP | módulo possui uma razão coesa para mudar; dividir services, schemas e adapters amplos |
| OCP | novo provedor implementa port sem alterar o use case |
| LSP | adapters/fakes preservam ausência, erros, ordenação e transação do contrato |
| ISP | ports focados; consumidor não depende de métodos que não usa |
| DIP | aplicação depende de abstrações internas; infraestrutura implementa |

Sinais de violação: `Session` em use case, `Depends` na aplicação, `HTTPException` no domínio, commit oculto, ORM em output ou adapter instanciado dentro da regra.

## 12. Tipagem Python

- **MUST** tipar parâmetros e retornos de domínio, aplicação, ports e adapters.
- **MUST** usar `X | None` somente para opcionalidade real.
- **MUST** parametrizar collections: `list[Budget]`, `dict[int, Decimal]`.
- **MUST** evitar `Any` e `dict[str, Any]` quando a estrutura for conhecida.
- **SHOULD** usar `Protocol`, dataclass e `TypedDict` conforme a semântica.
- **SHOULD** usar `Enum`/`StrEnum` para estados finitos.
- **MUST NOT** usar `cast()` ou `# type: ignore` sem motivo e escopo mínimo.
- **SHOULD** adotar mypy progressivamente, iniciando em `domain` e `application`.

## 13. Tratamento de erros

```text
Domain/Application Error → exception handler da API → resposta HTTP estável
```

- **MUST** manter domínio livre de `HTTPException`.
- **MUST** distinguir regra inválida, conflito, não encontrado e dependência indisponível.
- **MUST** encadear causa técnica com `raise ... from exc`.
- **MUST** garantir rollback pelo Unit of Work.
- **MUST** não expor stack, SQL, URL sensível ou mensagem do driver.
- **SHOULD** padronizar `{"detail": "...", "code": "...", "trace_id": "..."}`.
- **MUST** registrar detalhe técnico apenas em log seguro e redigido.

## 14. Dependency Injection e configuração

- **MUST** usar constructor injection em casos de uso.
- **MUST** construir sessão, repositories, gateways e use case na borda.
- **MUST** compartilhar sessão/UoW entre adapters da mesma transação.
- **MUST NOT** usar Service Locator, singleton mutável ou `Depends` no núcleo.
- **SHOULD** injetar relógio, IDs e tokens quando afetarem comportamento.
- **MUST** carregar configuração com `pydantic-settings` e falhar em valor obrigatório/inseguro.
- **MUST** representar segredos com `SecretStr` e nunca ter fallback fraco.
- **MUST** validar configurações de produção, TLS, CORS e bypasses.
- **MUST** usar logging consistente com correlation ID e redaction de PII.

## 15. Testes e qualidade

| Tipo | Deve cobrir |
|---|---|
| domínio | invariantes, VOs, transições e cálculos, sem mocks |
| aplicação | casos de uso com fakes dos ports |
| adapter | mapping, erros técnicos e integração controlada |
| PostgreSQL | repositories, constraints, migrations, rollback e concorrência |
| API | status, schema, auth, autorização, validação e errors |
| E2E | fluxo crítico cliente → orçamento → OS → execução → fatura |
| arquitetura | regras de imports e camadas |

- **MUST** escrever/atualizar testes antes ou junto da implementação.
- **MUST** testar comportamento observável, caminhos felizes, limites e falhas.
- **MUST** manter testes determinísticos e independentes de ordem/rede.
- **MUST** usar PostgreSQL migrado; SQLite pode complementar, não substituir.
- **MUST** manter pelo menos 80% global com branch coverage habilitada.
- **MUST** cobrir decisões críticas de auth, billing, validação e segurança.
- **SHOULD** nomear `test_<resultado>_when_<condição>`.

Toolchain alvo: Ruff (`format --check` e `check`), mypy, pytest com branch coverage e `--cov-fail-under=80`, `alembic check`, Bandit e pip-audit, sempre via Poetry.

O CI deve executar esses gates, PostgreSQL/Alembic, build/testes frontend e build Docker.

## 16. Code smells

| Smell | Sinal principal |
|---|---|
| Long Method/Large Class | muitas etapas, efeitos ou razões para mudar |
| Feature Envy | comportamento usa mais dados de outro objeto |
| Data Clumps/Primitive Obsession | parâmetros/primitivos escondem conceito |
| Shotgun Surgery | pequena regra exige alterações espalhadas |
| Message Chains | conhecimento excessivo de estrutura interna |
| Middle Man | delegação sem política ou limite protegido |
| Speculative Generality | abstração/generic sem consumidor real |
| N+1 | query por item em lista/loop |
| Vazamento de infraestrutura | ORM/HTTP atravessa para o núcleo |

Smell exige investigação, não refatoração automática.

## 17. Refatoração

- **MUST** preservar comportamento observável.
- **MUST** criar testes de caracterização antes de alterar legado arriscado.
- **MUST** trabalhar em passos pequenos com testes verdes.
- **SHOULD** separar mudança estrutural de funcional quando facilitar revisão.

Use:

- **Extract Function** para intenção nomeável.
- **Extract Class** para motivos de mudança independentes.
- **Move Function** quando usa principalmente dados de outro módulo.
- **Introduce Parameter Object** para parâmetros que formam conceito.
- **Replace Primitive with Object** para dinheiro, documento ou unidade.
- **Replace Conditional with Polymorphism** somente para variações reais e crescentes.

## 18. Design Patterns

| Pattern | Quando usar | Evitar |
|---|---|---|
| Repository | coleção de agregados sem expor persistência | CRUD genérico por tabela |
| Unit of Work | operação atômica entre adapters | leitura simples |
| Adapter | banco, API, SMTP, PDF e token | função pura |
| DI | selecionar implementação na borda | locator global |
| Factory | criação possui invariantes | construtor já é claro |
| Strategy | política/provedor realmente variável | único `if` estável |
| Facade | entrada fina para subsistema coeso | esconder God Object |
| Specification | filtros combináveis e reutilizados | consulta simples isolada |

Patterns resolvem problemas; não são metas de quantidade.

## 19. Anti-patterns e dívidas atuais

### Não fazer

- Regra de negócio em route ou repository.
- Domínio importando FastAPI, Pydantic, ORM ou infraestrutura.
- Use case retornando HTTP/ORM ou acessando sessão.
- Repository fazendo commit.
- Adapter instanciado dentro da regra.
- `GenericRepository` universal ou `utils.py` sem responsabilidade.
- `except Exception: pass`, SQL concatenado, segredo hardcoded ou PII em log.
- `float` para dinheiro, `GET` mutável ou token público em texto puro.

### Dívidas que não devem ser copiadas

| Área atual | Direção recomendada |
|---|---|
| transições de `Budget`/OS incompletas | policy explícita e testes |
| `BudgetService`/`BudgetApprovalService` amplos | casos de uso por intenção |
| filhos de `Budget` alterados externamente | métodos do aggregate root |
| OS criada diretamente como ORM | factory de domínio + repository |
| `BudgetRepository`/`InventoryRepository` amplos | segregar quando ciclos divergirem |
| `schemas.py` e `database.py` monolíticos | módulos por contexto |
| error handlers duplicados | handler global uniforme |
| UoW sem rollback automático | context manager transacional |
| SMTP antes do commit | efeito idempotente ou outbox |
| `Float` e timestamps naive | `Decimal/Numeric` e UTC aware |
| drift ORM/Alembic | PostgreSQL migrado + contract tests |
| estoque/aprovação sem controle concorrente | SQL condicional/lock/versionamento |
| token de aprovação bruto | fingerprint, expiração e uso único |
| PII em logs e auth sem RBAC/rate limit | redaction, policies e hardening |
| SQLite como única integração | PostgreSQL + Alembic |
| Docker sem `.dockerignore` | contexto mínimo, usuário não-root, migration job único |
| sem Ruff/mypy/coverage gate | tooling versionado e CI |
