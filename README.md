# Oficina Mecânica — Sistema Integrado de Atendimento

Backend MVP para gestão de ordens de serviço (OS), clientes, veículos, peças/insumos e faturamento.

**FIAP 15SOAT — Tech Challenge Fase 1**

## Stack

- Python 3.12 + FastAPI
- PostgreSQL (escolhido por suporte a transações ACID, integridade referencial e escalabilidade para filas de OS)
- SQLAlchemy + Alembic
- JWT de curta duracao em cookie HttpOnly + refresh token opaco rotativo em cookie HttpOnly
- Docker + docker-compose
- MailHog para email em desenvolvimento

## Arquitetura

Monolito em camadas:

```
src/
  domain/         # regras de negócio, enums, validadores
  application/    # casos de uso / services
  infrastructure/ # banco, auth, email, PDF
  api/            # routers FastAPI e schemas
```

## Executar com Docker

```bash
cp .env.example .env
# Edite .env e defina SECRET_KEY (>= 32 caracteres aleatórios) e POSTGRES_PASSWORD
docker compose up db mailhog redis -d
docker compose run --rm api alembic upgrade head
docker compose run --rm -e DEV_ADMIN_PASSWORD=<senha-forte> api python -m src.scripts.seed_dev_admin
docker compose up --build
```

- API (Docker): http://localhost:8000
- API (local `poetry run uvicorn`): http://localhost:8000
- Swagger: http://localhost:8000/docs
- MailHog UI: http://localhost:8025

O `docker compose run` do seed substitui o `CMD` da imagem, então o Alembic precisa rodar **antes** do seed. Na subida normal (`docker compose up`), as migrations também rodam no start do container `api`.

As migrations do Alembic rodam automaticamente na subida do container `api`. Para aplicar só as migrations, use `docker compose run --rm api alembic upgrade head`.

Ao rodar a API localmente fora do Docker, use `SMTP_HOST=localhost`. O host `mailhog` funciona apenas dentro da rede do Docker Compose.

## Executar localmente

Instale o [Poetry](https://python-poetry.org/docs/#installation) e depois:

```bash
poetry install
cp .env.example .env
# Edite .env e defina SECRET_KEY com pelo menos 32 caracteres aleatórios
# Subir o banco: docker compose up db -d  (ou PostgreSQL local)
# DATABASE_URL usa localhost fora do Docker; dentro do Compose use host db
poetry run alembic upgrade head   # aplica todas as migrations pendentes
DEV_ADMIN_PASSWORD=<senha-forte> poetry run python -m src.scripts.seed_dev_admin
poetry run python -m src.scripts.promote_first_admin  # comando explicito de break-glass
poetry run uvicorn src.main:app --reload --host 127.0.0.1 --port 8000
```

No PowerShell, use:

```powershell
$env:DEV_ADMIN_PASSWORD="<senha-forte>"
poetry run python -m src.scripts.seed_dev_admin
```

## Autenticação

O usuário admin não é criado automaticamente. Em um banco novo, rode o seed após as migrations:

```bash
DEV_ADMIN_PASSWORD=<senha-forte> poetry run python -m src.scripts.seed_dev_admin
```

No PowerShell:

```powershell
$env:DEV_ADMIN_PASSWORD="<senha-forte>"
poetry run python -m src.scripts.seed_dev_admin
```

Credenciais após o seed:

- **Usuário:** `admin`
- **Senha:** valor definido em `DEV_ADMIN_PASSWORD`

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"<senha-forte>"}'
```

O login nao devolve tokens no JSON. A API define cookies `oficina_access`, `oficina_refresh` e `oficina_csrf`; clientes enviam `X-CSRF-Token` em operacoes mutaveis. Use `POST /api/v1/auth/refresh`, `POST /api/v1/auth/logout` e `GET /api/v1/admin/me` para renovar, encerrar e consultar a sessao.

Se receber `Credenciais inválidas` em banco novo, verifique:

1. `poetry run alembic upgrade head` foi executado.
2. `DEV_ADMIN_PASSWORD` foi definido antes de rodar o seed.
3. `python -m src.scripts.seed_dev_admin` criou o usuário admin.
4. A API está usando o mesmo `DATABASE_URL` onde o seed foi executado.

## Gestão de clientes (T02 — RF01 + RF05)

Cada cliente possui **um ou mais documentos** (CPF e/ou CNPJ). O tipo é inferido pelo tamanho do documento (11 = CPF, 14 = CNPJ); não há campo `person_type`. Regras de domínio:

- No máximo **um CPF** por cliente; **vários CNPJs** permitidos
- Documento duplicado no sistema → HTTP 409
- Endereço **obrigatório** no cadastro
- CPF validado estruturalmente em desenvolvimento; em produção, também é validado externamente via [Invertexto API](docs/cpf-validation-invertexto.md)
- CNPJ validado externamente via [Brasil API](https://brasilapi.com.br/docs) antes de persistir

### APIs administrativas (JWT)

| Método | Rota | Descrição |
|--------|------|-----------|
| `POST` | `/api/v1/admin/customers` | Criar cliente |
| `GET` | `/api/v1/admin/customers` | Listar clientes |
| `GET` | `/api/v1/admin/customers/{id}` | Buscar por ID |
| `PUT` | `/api/v1/admin/customers/{id}` | Atualizar contato |
| `DELETE` | `/api/v1/admin/customers/{id}` | Remover cliente |
| `POST` | `/api/v1/admin/customers/by-document` | Buscar por CPF/CNPJ (documento no corpo) |
| `POST` | `/api/v1/admin/customers/validate-cpf` | Pré-validar CPF (documento no corpo) |
| `POST` | `/api/v1/admin/customers/validate-cnpj` | Pré-validar CNPJ (documento no corpo) |
| `POST` | `/api/v1/admin/customers/{id}/documents` | Adicionar documento a cliente existente |

Exemplo de criação:

```bash
curl -X POST http://localhost:8000/api/v1/admin/customers \
  -b cookies.txt -H "X-CSRF-Token: <oficina_csrf>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Maria Silva",
    "document": "529.982.247-25",
    "email": "maria@test.com",
    "phone": "11999999999",
    "address": "Rua A, 100"
  }'
```

Resposta admin inclui `documents: ["52998224725"]` (lista normalizada, sem máscara).

### API pública

| Método | Rota | Descrição |
|--------|------|-----------|
| `POST` | `/api/v1/customers/lookup` | Identificar cliente por documento + segundo fator |

Por segurança, a rota pública retorna apenas `{ "id", "name" }` — sem e-mail, telefone ou endereço.

## Gestão de veículos (T03 — RF02)

Veículos vinculados a clientes cadastrados (T02). Regras de domínio:

- Placa validada nos formatos **legado** (`ABC1234`) e **Mercosul** (`ABC1D23`)
- Placa inválida → HTTP 422 com mensagem `Veículo inválido`
- Não pode haver dois veículos com a **mesma placa para o mesmo cliente** → HTTP 409
- UF validada contra siglas brasileiras (2 letras)

### APIs administrativas (JWT)

| Método | Rota | Descrição |
|--------|------|-----------|
| `POST` | `/api/v1/admin/vehicles` | Cadastrar veículo |
| `GET` | `/api/v1/admin/vehicles` | Listar todos os veículos |
| `GET` | `/api/v1/admin/vehicles/{id}` | Buscar veículo por ID |
| `PUT` | `/api/v1/admin/vehicles/{id}` | Atualizar veículo |
| `DELETE` | `/api/v1/admin/vehicles/{id}` | Remover veículo |
| `GET` | `/api/v1/admin/customers/{id}/vehicles` | Listar veículos do cliente |

Exemplo de criação:

```bash
curl -X POST http://localhost:8000/api/v1/admin/vehicles \
  -b cookies.txt -H "X-CSRF-Token: <oficina_csrf>" \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": 1,
    "plate": "ABC1D23",
    "state": "SP",
    "city": "São Paulo",
    "color": "Prata",
    "brand": "VW",
    "model": "Gol",
    "year": 2021
  }'
```

No painel Angular, selecione um cliente em **Clientes** para listar e cadastrar veículos associados.

## Faturamento e encerramento (T11 — RF38–RF40)

Após finalizar a OS (`PATCH /admin/service-orders/{id}/finish`), o atendimento pode emitir fatura, registrar pagamento e encerrar a OS como entregue.

### APIs administrativas (JWT)

| Método | Rota | Descrição |
|--------|------|-----------|
| `POST` | `/api/v1/admin/service-orders/{id}/invoice` | Gerar fatura para OS finalizada |
| `GET` | `/api/v1/admin/service-orders/{id}/invoice` | Consultar fatura da OS |
| `PATCH` | `/api/v1/admin/invoices/{id}/pay` | Registrar pagamento integral |
| `PATCH` | `/api/v1/admin/service-orders/{id}/deliver` | Entregar OS (fatura deve estar paga) |

O pagamento integral altera automaticamente o status da OS para `Entregue`.

## Painel web Angular (admin completo)

Frontend em **Angular 15** com CRUD master-detail para todas as entidades administrativas.

```bash
cd frontend
npm install
npm start
```

- **URL:** http://localhost:4200
- Login: `admin` / senha definida em `DEV_ADMIN_PASSWORD`
- Proxy dev encaminha `/api/*` → `http://localhost:8000`

Rotas: clientes, veículos, serviços, produtos, fornecedores, orçamentos e ordens de serviço. Detalhes em `frontend/README.md`.

## Painel web legado (T02)

Interface vanilla servida pelo FastAPI em `/app/`:

- **URL (local):** http://localhost:8000/app/
- **URL (Docker):** http://localhost:8000/app/
- Login com `admin` / senha definida em `DEV_ADMIN_PASSWORD`
- Cadastro de clientes (CPF ou CNPJ), validação externa de CPF/CNPJ, busca por documento e listagem

> **Nota:** Se o container Docker `api` estiver rodando, `http://localhost:8000` responde pelo Docker. Pare o container com `docker compose stop api` para usar o uvicorn local.

## Fluxos principais

1. Cadastrar cliente, veículo, serviços e produtos
2. Criar orçamento com linhas de serviço/produto
3. Enviar orçamento por email (aprovação/recusa via link público)
4. OS gerada automaticamente na aprovação
5. Atribuir mecânico, reservar peças, executar serviço
6. Gerar fatura e registrar pagamento → OS entregue

## Hardening de OS e links publicos

- OS segue `Recebida -> Em diagnostico -> Aguardando aprovacao -> Aguardando inicio -> Em execucao -> Finalizada -> Entregue`.
- A primeira atribuicao de mecanico move a OS para diagnostico; trocas posteriores exigem motivo e nao regridem o status.
- Revisoes de orcamento enviadas sao imutaveis. A decisao publica usa `POST /api/v1/public/budgets/decisions` com `{token, decision}` e e idempotente.
- Tracking usa `POST /api/v1/public/service-orders/track` com token no corpo, fingerprint HMAC no banco, revogacao no reenvio e expiracao contada desde a emissao.
- Tokens de aprovacao, refresh e tracking possuem segredos separados. O token bruto nao aparece em respostas administrativas nem em colunas do banco.
- O override de status exige papel `ADMIN`, motivo e so permite os tres estados iniciais; cada transicao e registrada em historico append-only.

## Testes

```bash
poetry run pytest --cov=src --cov-branch --cov-report=term-missing --cov-fail-under=80
```

## Segurança

Relatório de vulnerabilidades em `docs/security-report.md` (Bandit + pip-audit).

## Requisitos funcionais

Implementação cobre RF01–RF40 conforme plano de tarefas do projeto.
