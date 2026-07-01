# Arquitetura e Padrões do Projeto

> Documento gerado a partir da leitura de `docs/` (contexts, database, security) e validado contra a estrutura real de `src/` e `frontend/`. Reflete o entendimento do estado do projeto em 2026-06-30, branch `T08-Gestao-OS`.

## Visão geral

Sistema integrado de gestão para uma oficina mecânica (Tech Challenge Fase 1 — FIAP 15SOAT), cobrindo o ciclo completo: cadastro de clientes/veículos → orçamento → aprovação → Ordem de Serviço (OS) → estoque/compras → execução → faturamento. 40 requisitos funcionais (RF01–RF40) documentados em `docs/contexts/requirements/requirements.md`, decompostos em 13 tarefas de desenvolvimento (T01–T12) em `docs/contexts/tasks/tasks.md`, todas marcadas como `completed`.

## Stack

- **Backend:** Python 3.12 + FastAPI, monolito em camadas, REST + OpenAPI/Swagger
- **Banco:** PostgreSQL (escolhido por ACID, integridade referencial, escalabilidade de filas de OS) + SQLAlchemy + Alembic
- **Auth:** JWT (`python-jose`) nas rotas `/api/v1/admin/*`
- **PDF:** ReportLab (orçamentos e OS)
- **E-mail:** SMTP (MailHog em dev)
- **Frontend:** Angular 15 (painel admin completo) + um painel legado "vanilla JS" servido em `/app/` pelo próprio FastAPI (remanescente da T02)
- **Infra:** Docker + docker-compose
- **Qualidade:** pytest (meta de 80% de cobertura nos domínios críticos), Bandit (SAST) e pip-audit (dependências)

## Arquitetura em camadas (estilo hexagonal/DDD-light)

```
src/
  domain/          # entidades, value objects, regras de negócio, enums de status
  application/      # casos de uso (services) + ports (interfaces/contratos)
  infrastructure/    # adapters: SQLAlchemy, JWT, e-mail, PDF, APIs externas
  api/              # routers FastAPI, schemas Pydantic, composição de dependências (DI)
```

Cada contexto de domínio (`customer`, `vehicle`, `product`, `supplier`, `service_catalog`, `budget`, `service_order`, `inventory`, `execution`, `billing`, `auth`) segue o mesmo padrão de pastas: `entity.py` + `repository.py` (interface) dentro de `domain/<contexto>/`, com o adapter concreto em `infrastructure/persistence/<contexto>_repository.py`.

**Fluxo de dependência:** `api` → `application` (services, via `ports`) → `domain` (regras puras) ← `infrastructure` (implementa os `ports`). A composição das dependências concretas acontece em `src/api/composition/<contexto>.py` (injeção manual, sem framework de DI).

### Padrões identificados

- **Ports & Adapters:** `application/ports/*.py` define interfaces (`email.py`, `pdf_generator.py`, `cpf_validator.py`, `cnpj_validator.py`, `unit_of_work.py`, etc.); `infrastructure/` implementa os adapters concretos. Permite trocar provedor de validação de CPF/CNPJ, e-mail ou PDF sem tocar nos casos de uso.
- **Aggregate Root:** OS (`service_order`) é o agregado raiz que centraliza cliente, veículo, diagnóstico e linhas de serviço/produto (RF07). Orçamento (`budget`) segue padrão similar para suas linhas.
- **Unit of Work:** `application/ports/unit_of_work.py` + `infrastructure/persistence/unit_of_work.py` coordenam transações multi-repositório (ex.: aprovação de orçamento → criação de OS).
- **Máquina de estados:** OS e Orçamento têm status como string controlada por enum (`domain/enums.py`), com transições validadas nos métodos da entidade (ex.: `Budget.approve()`, `mark_sent()`). O hardening review (item 7) aponta que essas transições ainda não bloqueiam todos os caminhos inválidos (ex.: orçamento aprovado pode ser recusado depois).
- **Reserva lógica de estoque:** Estoque Disponível = Estoque Físico − Reservas Ativas (RF13/RF20/RF25), nunca decrementando o estoque físico até a retirada real — evita ruptura por concorrência entre OS.
- **Geração automática orientada a eventos/transição de estado:** aprovação de orçamento → cria OS (RF18); falta de estoque → gera Solicitação de Compra automaticamente (RF23); aprovação de Pedido de Compra → gera Recebimento (RF24). Implementado como orquestração síncrona dentro dos services de aplicação, não como barramento de eventos real.
- **Tokens de aprovação pública:** orçamentos têm `approval_token` único, usado em links de e-mail (`GET /public/budgets/{token}/approve|reject`) para aprovação sem autenticação — mas atualmente como token bruto em texto puro no banco e exposto via GET mutável (ver Débitos técnicos).

## Modelo de dados

Ver `docs/database/database-schema.mermaid`. Principais agregados e relações:

- `customers` 1—N `vehicles`, `budgets`, `service_orders`
- `budgets` (Rascunho/Enviado/Aprovado/Recusado) 1—N `budget_service_lines`, `budget_product_lines`; pode gerar 0..1 `service_orders`
- `service_orders` (Recebida → Em diagnóstico → Aguardando aprovação → Em execução → Finalizada → Entregue) referencia linhas de serviço/produto próprias, `reservations`, `stock_withdrawals`, `purchase_requests` e 1 `invoice`
- `products` ligados a `suppliers`, com `service_product_lines` (BOM: produtos associados a um serviço de catálogo)
- `purchase_requests` → `goods_receipts` (recebimento de compras)

Particularidade de modelagem: **cliente não tem campo `person_type`**; o tipo de documento (CPF/CNPJ) é inferido pelo tamanho da string (11 ou 14 dígitos). Um cliente pode ter no máximo 1 CPF, mas vários CNPJs.

## Fluxo de status da OS

```
Recebida → Em Diagnóstico → Aguardando Aprovação → Em Execução → Finalizada → Entregue
```

Transições automáticas disparadas por ações: atribuir mecânico (RF26/RF27), aprovação vinculada de orçamento (RF18/RF31), finalização de atendimento + reconciliação de estoque (RF33/RF37), pagamento de fatura (RF39/RF40).

## Validações externas (integrações)

- **CPF:** Invertexto API (`infrastructure/external/invertexto_cpf.py`), autenticada por token de query string
- **CNPJ:** Brasil API (`infrastructure/external/brasil_api_cnpj.py`), sem autenticação
- Ambas seguem o mesmo padrão: validação local de dígito verificador (`validate_docbr`) → checagem de duplicidade no banco → validação externa antes de persistir. Documentado em detalhe em `docs/contexts/others/cpf-validation-invertexto.md`.

## Segurança — estado atual

`docs/security/security-report.md` resume o scan (Bandit: 0 issues em 5902 linhas; pip-audit). Pontos mitigados: SQL injection (ORM parametrizado), CORS restrito (parcialmente), input validation de CPF/CNPJ/placa no domínio.

`docs/contexts/others/hardening-review.md` (28/06/2026) lista um backlog de hardening ainda não resolvido — útil para saber **o que ainda não está pronto para produção**:

**Bloqueadores:**
1. Admin padrão (`admin/admin123`) criado automaticamente no startup/login; `SECRET_KEY` com fallback fraco (`dev-secret-key`)
2. Endpoints públicos `GET` que mutam estado (`approve`/`reject` de orçamento) — vulnerável a crawlers/prefetch
3. Token de aprovação armazenado em texto puro, sem expiração persistida nem uso único
4. CPF/CNPJ logados em texto puro (incluindo em URLs)

**Débito de DDD/clean architecture:**
5. `BudgetApprovalService` concentra responsabilidades demais (token, e-mail, PDF, mudança de estado, commit)
6. `SqlAlchemyBudgetRepository` mistura múltiplos ports num único arquivo
7. Falta política explícita de transições de estado (orçamento aprovado pode ser recusado em seguida)
8. `api/schemas.py` é um arquivo monolítico com DTOs de todos os contextos

**Frontend:**
9. JWT em `localStorage` (risco de XSS)
10. UX de erro global via `alert()` do navegador
11. Componente de detalhe de OS mistura responsabilidades de gestão (T08) e faturamento (T11)

**Infra:**
12. CORS hardcoded em `src/main.py`
13. `Base.metadata.create_all()` roda no startup da app (deveria ser só Alembic fora de dev/teste)
14. `get-pip.py` versionado na raiz do repositório

## Convenções de projeto observadas

- **Camadas:** lógica de negócio fica em `domain/`/`application/`, nunca nos handlers dos routers (regra explícita na "Definição de pronto" de `tasks.md`)
- **Rotas:** `/api/v1/admin/*` exigem JWT; rotas públicas (aprovação por token, tracking por documento) não exigem autenticação mas restringem os dados retornados (ex.: busca pública por documento retorna só `{id, name}`)
- **Migrations:** Alembic obrigatório para novas tabelas (ainda que `create_all()` no startup seja um desvio identificado como débito)
- **Testes:** unitários para validadores/cálculos/transições de estado; integração para os fluxos ponta-a-ponta (orçamento → aprovação → OS → execução → fatura)
- **Rastreabilidade:** cada tarefa de desenvolvimento (T01–T12) está mapeada 1:N para RFs específicos, com tabela de índice completa em `tasks.md`

## Lacunas / perguntas em aberto

`docs/contexts/others/open_questions.md` registra pendências de requisito ainda sem resposta definitiva:
- Duplicidade de CPF/CNPJ entre clientes
- Campos obrigatórios/opcionais no cadastro de cliente
- Onde atualizar dados de usuário
- Necessidade de controle de lote/validade de produto em estoque
- Exposição do histórico de ajuste de estoque via API
