# Backlog de Revisão de Hardening

Escopo da revisão: codebase inteiro, com foco em clean code, fronteiras DDD e segurança.

> Status atual (2026-08): os itens de transição de OS, revisões de orçamento,
> tokens públicos, sessões por cookie e redação de PII foram implementados nas
> migrations 010 e 011. O contrato vigente usa `POST /public/budgets/decisions`,
> `POST /public/service-orders/track`, cookies HttpOnly/CSRF e fingerprints HMAC.
> Este arquivo permanece como histórico da auditoria; consulte o README e
> `docs/security/security-report.md` para os contratos vigentes.

> Fechamento da rodada de code review (2026-08-21). Também foram endereçados:
> item 7 (política de transição agora vive no agregado — `ServiceOrder._REVISABLE_STATUSES`
> e `ensure_can_apply_budget_revision`), item 12 (CORS com métodos e headers
> explícitos, mais `Content-Security-Policy`), e o `RefreshSessionService`
> passou a ser composto por `api/composition/auth.py` como os demais contextos.
> Item 10 (`alert()` global) também foi encerrado: o interceptor agora publica
> em `NotificationService`, renderizado por `app-notifications`.
> **Continuam abertos:** item 5 (`BudgetApprovalService` ainda concentra token,
> e-mail, PDF e commit), item 6 (`SqlAlchemyBudgetRepository` mistura ports),
> item 8 (`api/schemas.py` monolítico) e item 11 (detalhe de OS mistura T08 e T11).

Data: 2026-06-28

Formato dos itens:
- **Problema:** o que está errado e por que importa.
- **Ocorrências:** arquivos e linhas onde o problema aparece hoje.
- **Correção esperada:** direção de correção para a fase de hardening.

## Bloqueadores para produção

### 1. Remover credenciais administrativas padrão em produção

**Problema:**
- A aplicação cria usuário administrativo padrão com senha conhecida.
- A criação acontece automaticamente no startup e também no login.
- A chave JWT tem valor padrão fraco (`dev-secret-key`).
- Documentação e frontend legado expõem `admin/admin123`, o que normaliza credenciais inseguras.

**Ocorrências:**
- `src/application/services/auth_service.py:28` chama `ensure_default_admin()` durante `login()`.
- `src/application/services/auth_service.py:41` define `ensure_default_admin()`.
- `src/application/services/auth_service.py:46-48` cria usuário `admin` com senha `admin123`.
- `src/main.py:47` chama `compose_auth_service(db).ensure_default_admin()` no startup.
- `src/config.py:8` define `secret_key: str = "dev-secret-key"`.
- `src/infrastructure/auth/jwt.py:24` assina JWT usando `settings.secret_key`.
- `src/infrastructure/auth/jwt.py:28` valida JWT usando `settings.secret_key`.
- `src/infrastructure/auth/tokens.py:15` assina token de aprovação usando `settings.secret_key`.
- `src/infrastructure/auth/tokens.py:19` valida token de aprovação usando `settings.secret_key`.
- `README.md:57`, `README.md:62`, `README.md:127`, `README.md:138` documentam `admin/admin123`.
- `frontend/README.md:20` documenta `admin/admin123`.
- `frontend/legacy-panel/index.html:26` exibe dica com `admin/admin123`.
- `frontend/legacy-panel/index.html:34` pré-preenche senha `admin123`.

**Correção esperada:**
- Remover criação automática de admin do startup e do login.
- Criar comando explícito de seed para ambientes locais/testes.
- Exigir `SECRET_KEY` forte via variável de ambiente em ambientes não locais.
- Falhar rápido se `SECRET_KEY` estiver vazio ou igual ao valor padrão fora de teste/dev.
- Remover credenciais padrão da documentação de produção e do painel legado.

### 2. Substituir endpoints públicos GET que alteram estado

**Problema:**
- Endpoints públicos GET aprovam ou recusam orçamento, alterando estado do banco.
- `approve` cria OS.
- `reject` também altera estado.
- E-mail scanners, crawlers ou prefetchers podem abrir links GET automaticamente e aprovar/recusar orçamento sem ação consciente do cliente.

**Ocorrências:**
- `src/api/routers/budgets.py:218` declara `GET /{token}/approve`.
- `src/api/routers/budgets.py:219` define handler `approve_budget`.
- `src/api/routers/budgets.py:221` executa `compose_budget_approval_service(db).approve_budget(token)`.
- `src/application/services/budget_approval_service.py:96-105` aprova orçamento e cria OS.
- `src/api/routers/budgets.py:227` declara `GET /{token}/reject`.
- `src/api/routers/budgets.py:228` define handler `reject_budget`.
- `src/api/routers/budgets.py:230` executa `compose_budget_approval_service(db).reject_budget(token)`.
- `src/application/services/budget_approval_service.py:107-115` recusa orçamento e faz commit.

**Correção esperada:**
- GET deve renderizar uma página/tela de confirmação, sem mutar estado.
- POST deve executar a mutação:
  - `POST /api/v1/public/budgets/{token}/approve`
  - `POST /api/v1/public/budgets/{token}/reject`
- A tela de confirmação deve exigir ação explícita do cliente.
- Combinar com token de uso único e expiração do item 3.

### 3. Fortalecer tokens de aprovação

**Problema:**
- Token de aprovação é armazenado em texto puro no banco.
- Não há expiração persistida.
- Não há `used_at`, `approved_at` ou `rejected_at`.
- Token aparece em response administrativa de orçamento.
- Busca compara token bruto diretamente no banco.

**Ocorrências:**
- `src/api/schemas.py:247` expõe `approval_token` em `BudgetResponse`.
- `src/domain/budget/entity.py:93` mantém `approval_token` no agregado.
- `src/domain/budget/entity.py:149-151` `mark_sent()` salva token bruto e muda status para `SENT`.
- `src/infrastructure/database.py:159` coluna `approval_token` é `String(255)`, única e nullable.
- `src/infrastructure/persistence/budget_repository.py:34` persiste token bruto no `add()`.
- `src/infrastructure/persistence/budget_repository.py:47-50` consulta por igualdade direta do token bruto.
- `src/infrastructure/persistence/budget_repository.py:209` atualiza `approval_token` bruto.
- `src/infrastructure/persistence/budget_repository.py:223` carrega token bruto para domínio.
- `src/application/services/budget_approval_service.py:42-43` gera token e salva em `budget.mark_sent(token)`.
- `src/application/services/budget_approval_service.py:97` busca orçamento por token bruto para aprovação.
- `src/application/services/budget_approval_service.py:108` busca orçamento por token bruto para recusa.
- `src/infrastructure/budget_approval.py:25-26` gera token assinado.
- `src/infrastructure/auth/tokens.py:13-19` cria/decodifica token, mas não resolve persistência com hash/expiração/uso único.

**Correção esperada:**
- Armazenar hash do token, não token bruto.
- Adicionar colunas `approval_token_hash`, `approval_expires_at`, `approval_used_at`, `approved_at`, `rejected_at`.
- Remover `approval_token` da resposta administrativa, ou expor apenas quando estritamente necessário no envio.
- Rejeitar token expirado, reutilizado ou vinculado a orçamento terminal.
- Testar aprovação e recusa duplicadas, expiradas e fora de estado válido.

### 4. Parar de registrar CPF/CNPJ bruto em logs

**Problema:**
- Logs registram CPF/CNPJ completo.
- Log de CNPJ também registra URL contendo o documento.
- Isso expõe dados pessoais em observabilidade, CI, console local e arquivos de log.

**Ocorrências:**
- `src/infrastructure/external/invertexto_cpf.py:23` monta params com CPF bruto.
- `src/infrastructure/external/invertexto_cpf.py:24-28` registra CPF bruto no log.
- `src/infrastructure/external/invertexto_cpf.py:51` registra CPF bruto em log de sucesso.
- `src/infrastructure/external/brasil_api_cnpj.py:23` monta URL com CNPJ bruto.
- `src/infrastructure/external/brasil_api_cnpj.py:24-29` registra CNPJ bruto e URL com CNPJ.
- `src/infrastructure/external/brasil_api_cnpj.py:49` registra CNPJ bruto em log de sucesso.

**Correção esperada:**
- Criar helper de mascaramento de documento.
- Logar somente documento mascarado.
- Nunca logar URL contendo documento.
- Exemplo: CPF `***.***.***-25`; CNPJ `**.***.***/0001-**`.

## Backlog de DDD e clean architecture

### 5. Separar responsabilidades do `BudgetApprovalService`

**Problema:**
- `BudgetApprovalService` concentra muitas responsabilidades de aplicação e composição.
- Ele gera token, muda estado, cria payload de PDF, monta HTML, envia e-mail, cria OS e faz commit.
- Essa concentração dificulta teste, evolução e leitura do workflow.

**Ocorrências:**
- `src/application/services/budget_approval_service.py:16` define `BudgetApprovalService`.
- `src/application/services/budget_approval_service.py:37` inicia `send_budget_email()` com orquestração grande.
- `src/application/services/budget_approval_service.py:42-44` gera token, altera estado e salva orçamento.
- `src/application/services/budget_approval_service.py:46-50` faz lookup de cliente/veículo e fallback silencioso para strings vazias.
- `src/application/services/budget_approval_service.py:52-69` monta payload de linhas de serviço/produto para PDF.
- `src/application/services/budget_approval_service.py:71-78` gera PDF, mas descarta bytes gerados.
- `src/application/services/budget_approval_service.py:80-86` constrói URLs e HTML do e-mail.
- `src/application/services/budget_approval_service.py:87-92` envia e-mail.
- `src/application/services/budget_approval_service.py:93` faz commit.
- `src/application/services/budget_approval_service.py:96-115` também aprova/recusa orçamento e cria OS.

**Correção esperada:**
- Extrair `BudgetEmailComposer` para assunto/texto/html.
- Extrair `BudgetPdfPayloadFactory` para mapear linhas.
- Validar ausência de cliente/veículo em vez de fallback silencioso.
- Usar bytes do PDF como anexo ou remover geração se não for enviada.
- Manter `BudgetApprovalService` como orquestrador fino.

### 6. Separar responsabilidades de persistência de orçamento

**Problema:**
- `SqlAlchemyBudgetRepository` mistura persistência do agregado, linhas de serviço, linhas de produto, lookups de disponibilidade e ownership.
- O arquivo vira adapter multiuso, crescendo com responsabilidades de vários ports.

**Ocorrências:**
- `src/infrastructure/persistence/budget_repository.py:23` define `SqlAlchemyBudgetRepository`.
- `src/infrastructure/persistence/budget_repository.py:27-59` trata agregado `Budget`.
- `src/infrastructure/persistence/budget_repository.py:63-128` trata linhas de serviço.
- `src/infrastructure/persistence/budget_repository.py:131-196` trata linhas de produto.
- `src/infrastructure/persistence/budget_repository.py:198-252` salva e mapeia o agregado.
- `src/infrastructure/persistence/budget_repository.py:255` define `SqlAlchemyVehicleOwnershipLookup` no mesmo arquivo.
- `src/infrastructure/persistence/budget_repository.py:268` define `SqlAlchemyBudgetCatalogLookup` no mesmo arquivo.
- `src/infrastructure/persistence/budget_repository.py:304` define `SqlAlchemyBudgetInventoryLookup` no mesmo arquivo.

**Correção esperada:**
- Separar adapters por port/contexto:
  - `BudgetRepository`
  - `BudgetLineRepository`
  - `BudgetCatalogLookup`
  - `BudgetInventoryLookup`
  - `VehicleOwnershipLookup`
- Manter cada arquivo com uma razão clara para mudar.

### 7. Adicionar políticas explícitas de transição de ciclo de vida

**Problema:**
- Métodos de domínio permitem transições inválidas ou incompletas.
- Orçamento aprovado pode ser recusado em seguida.
- Orçamento recusado pode ser aprovado se o fluxo chamar `approve()`.
- Não há política explícita de estados terminais.

**Ocorrências:**
- `src/domain/budget/entity.py:149-151` `mark_sent()` sempre muda para `SENT`, sem validar estado anterior.
- `src/domain/budget/entity.py:153-156` `approve()` só bloqueia se já está `APPROVED`; não bloqueia `REJECTED` ou estados inadequados.
- `src/domain/budget/entity.py:158-159` `reject()` sempre muda para `REJECTED`, inclusive após aprovação.
- `src/application/services/budget_approval_service.py:101-104` aprova e cria OS sem policy de estado explícita além do método atual.
- `src/application/services/budget_approval_service.py:112-114` recusa e faz commit sem policy de estado explícita além do método atual.

**Correção esperada:**
- Modelar transições permitidas no domínio.
- Exemplo: apenas `SENT` pode ir para `APPROVED` ou `REJECTED`.
- Estados terminais devem rejeitar novas transições.
- Criar testes para transições inválidas.
- Aplicar o mesmo padrão ao ciclo de vida da OS conforme T10/T11 avançarem.

### 8. Separar schemas monolíticos da API

**Problema:**
- `src/api/schemas.py` reúne DTOs de todos os contextos.
- Isso aumenta acoplamento acidental e dificulta manutenção por bounded context.

**Ocorrências:**
- `src/api/schemas.py:33-72` schemas de cliente/documentos.
- `src/api/schemas.py:78-101` schemas de veículo.
- `src/api/schemas.py:104-141` schemas de catálogo de serviços.
- `src/api/schemas.py:144-174` schemas de produtos.
- `src/api/schemas.py:177-198` schemas de fornecedores.
- `src/api/schemas.py:201-258` schemas de orçamento.
- `src/api/schemas.py:261-303` schemas de OS.
- `src/api/schemas.py:306-333` schemas de reservas/compras/retiradas de estoque.
- `src/api/schemas.py:356-369` schemas de faturamento/métricas.

**Correção esperada:**
- Separar por contexto:
  - `api/schemas/customers.py`
  - `api/schemas/vehicles.py`
  - `api/schemas/catalog_services.py`
  - `api/schemas/products.py`
  - `api/schemas/budgets.py`
  - `api/schemas/service_orders.py`
  - `api/schemas/inventory.py`
  - `api/schemas/billing.py`
- Atualizar routers para importar apenas schemas do próprio contexto.

## Backlog de hardening do frontend

### 9. Substituir armazenamento de token em `localStorage`

**Problema:**
- JWT em `localStorage` pode ser roubado por XSS.
- O interceptor envia token local para qualquer request relativa que comece com `api/`.

**Ocorrências:**
- `frontend/src/app/service/auth.service.ts:6` define `TOKEN_KEY`.
- `frontend/src/app/service/auth.service.ts:18` salva JWT em `localStorage`.
- `frontend/src/app/service/auth.service.ts:25` remove JWT no logout.
- `frontend/src/app/service/auth.service.ts:30` lê JWT de `localStorage`.
- `frontend/src/app/service/auth.interceptor.ts:16` lê token.
- `frontend/src/app/service/auth.interceptor.ts:17-20` adiciona `Authorization: Bearer` em requests `api/`.

**Correção esperada:**
- Preferir cookie httpOnly, secure e SameSite.
- Se JWT em storage permanecer temporariamente, adicionar CSP forte e sanitização/encoding rigorosos.
- Revisar escopo do interceptor para evitar envio indevido.

### 10. Substituir UX global de erro com `alert()`

**Problema:**
- Alertas globais do navegador são intrusivos, bloqueantes e difíceis de testar.
- O opt-out atual resolve o tracking público, mas o padrão global ainda é frágil.

**Ocorrências:**
- `frontend/src/app/service/http-error.interceptor.ts:24` checa `SKIP_GLOBAL_ERROR_ALERT`.
- `frontend/src/app/service/http-error.interceptor.ts:25` executa `alert(message)`.
- `frontend/src/app/service/http-error.interceptor.ts:33` define `SKIP_GLOBAL_ERROR_ALERT`.
- `frontend/src/app/service/service-order.service.ts:13` importa `SKIP_GLOBAL_ERROR_ALERT`.
- `frontend/src/app/service/service-order.service.ts:62` usa opt-out no tracking público.

**Correção esperada:**
- Introduzir `NotificationService`/toast.
- Remover `alert()` do interceptor.
- Manter erros esperados no componente que conhece o contexto.

### 11. Separar ações do detalhe de OS por workflow delimitado

**Problema:**
- Componente de detalhe de OS mistura T08 e T11.
- Atribuição/prioridade/e-mail pertencem à gestão da OS.
- Criar fatura/entregar pertencem a faturamento/encerramento.

**Ocorrências:**
- `frontend/src/app/component/service-orders/service-order-detail/service-order-detail.component.ts:11` define componente único.
- `frontend/src/app/component/service-orders/service-order-detail/service-order-detail.component.ts:44-64` salva mecânico/prioridade.
- `frontend/src/app/component/service-orders/service-order-detail/service-order-detail.component.ts:66-79` envia e-mail/PDF da OS.
- `frontend/src/app/component/service-orders/service-order-detail/service-order-detail.component.ts:81-85` cria fatura.
- `frontend/src/app/component/service-orders/service-order-detail/service-order-detail.component.ts:88-94` entrega OS.
- `frontend/src/app/component/service-orders/service-order-detail/service-order-detail.component.html:50-80` seção de edição T08.
- `frontend/src/app/component/service-orders/service-order-detail/service-order-detail.component.html:82-95` mistura ações de e-mail, fatura e entrega.

**Correção esperada:**
- Separar em painéis focados:
  - `ServiceOrderAssignmentPanel`
  - `ServiceOrderEmailPanel`
  - `ServiceOrderBillingPanel`
- Ou mover billing/delivery para tela/feature T11.

## Infraestrutura e higiene do repositório

### 12. Mover CORS para configuração

**Problema:**
- CORS está hardcoded no código principal.
- Métodos e headers estão amplos (`*`).
- Isso dificulta configurar ambientes e endurecer produção.

**Ocorrências:**
- `src/main.py:60-66` configura `CORSMiddleware` diretamente.
- `src/main.py:62` hardcode `allow_origins=["http://localhost:4200"]`.
- `src/main.py:64` usa `allow_methods=["*"]`.
- `src/main.py:65` usa `allow_headers=["*"]`.
- `frontend/docs/FRONTEND_BUILD_GUIDE.md:100-103` replica exemplo amplo.
- `frontend/docs/FRONTEND_BUILD_GUIDE.md:585-587` replica exemplo amplo.

**Correção esperada:**
- Mover origens CORS para `Settings`.
- Definir allowlist por ambiente.
- Restringir métodos e headers em produção.

### 13. Desabilitar `Base.metadata.create_all()` fora de dev/teste

**Problema:**
- A aplicação cria schema no startup.
- Isso contorna disciplina de migrações e pode mascarar drift de banco.

**Ocorrências:**
- `src/main.py:40` importa `Base`, `SessionLocal`, `engine` dentro do lifespan.
- `src/main.py:42` chama `Base.metadata.create_all(bind=engine)` no startup da aplicação.
- `tests/conftest.py:29` também chama `create_all`, mas neste caso é aceitável em testes.

**Correção esperada:**
- Usar Alembic em ambientes implantados.
- Permitir `create_all` só em testes/local bootstrap explícito.
- Adicionar config como `AUTO_CREATE_SCHEMA=false` por padrão fora de teste.

### 14. Remover `get-pip.py` da raiz

**Problema:**
- Script grande de bootstrap/vendor está versionado na raiz.
- Aumenta ruído do repositório e não pertence ao código da aplicação.

**Ocorrências:**
- `get-pip.py:1+` arquivo versionado na raiz.
- `get-pip.py:11` comentário interno do script confirma finalidade de bootstrap de pip.
- `get-pip.py:31` referência ao script oficial remoto.

**Correção esperada:**
- Remover `get-pip.py` do repositório.
- Documentar setup com Poetry/Python no README.
- Garantir `.gitignore` para artefatos/bootstrap locais.
