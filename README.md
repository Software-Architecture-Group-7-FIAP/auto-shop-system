# Oficina Mecânica — Sistema Integrado de Atendimento

Backend MVP para gestão de ordens de serviço (OS), clientes, veículos, peças/insumos e faturamento.

**FIAP 15SOAT — Tech Challenge Fase 1**

## Stack

- Python 3.12 + FastAPI
- PostgreSQL (escolhido por suporte a transações ACID, integridade referencial e escalabilidade para filas de OS)
- SQLAlchemy + Alembic
- JWT para APIs administrativas
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
# Edite .env e defina SECRET_KEY com pelo menos 32 caracteres aleatórios
docker compose up db mailhog -d
docker compose run --rm app poetry run alembic upgrade head
docker compose run --rm -e DEV_ADMIN_PASSWORD=admin123 app poetry run python -m src.scripts.seed_dev_admin
docker compose up --build
```

- API (Docker): http://localhost:8001
- API (local `poetry run uvicorn`): http://localhost:8000
- Swagger: http://localhost:8000/docs (local) or http://localhost:8001/docs (Docker)
- MailHog UI: http://localhost:8025

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
DEV_ADMIN_PASSWORD=admin123 poetry run python -m src.scripts.seed_dev_admin
poetry run uvicorn src.main:app --reload --host 127.0.0.1 --port 8000
```

No PowerShell, use:

```powershell
$env:DEV_ADMIN_PASSWORD="admin123"
poetry run python -m src.scripts.seed_dev_admin
```

## Autenticação

O usuário admin não é criado automaticamente. Em um banco novo, rode o seed após as migrations:

```bash
DEV_ADMIN_PASSWORD=admin123 poetry run python -m src.scripts.seed_dev_admin
```

No PowerShell:

```powershell
$env:DEV_ADMIN_PASSWORD="admin123"
poetry run python -m src.scripts.seed_dev_admin
```

Credenciais após o seed:

- **Usuário:** `admin`
- **Senha:** valor definido em `DEV_ADMIN_PASSWORD`

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'
```

Use o token JWT retornado no header `Authorization: Bearer <token>` para rotas `/api/v1/admin/*`.

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
| `GET` | `/api/v1/admin/customers/by-document/{documento}` | Buscar por CPF/CNPJ (dados completos) |
| `GET` | `/api/v1/admin/customers/validate-cpf/{cpf}` | Pré-validar CPF na Invertexto API |
| `GET` | `/api/v1/admin/customers/validate-cnpj/{cnpj}` | Pré-validar CNPJ na Brasil API |
| `POST` | `/api/v1/admin/customers/{id}/documents` | Adicionar documento a cliente existente |

Exemplo de criação:

```bash
curl -X POST http://localhost:8000/api/v1/admin/customers \
  -H "Authorization: Bearer <token>" \
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
| `GET` | `/api/v1/customers/by-document/{documento}` | Identificar cliente por documento |

Por segurança, a rota pública retorna apenas `{ "id", "name" }` — sem e-mail, telefone ou endereço.

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
- **URL (Docker):** http://localhost:8001/app/
- Login com `admin` / senha definida em `DEV_ADMIN_PASSWORD`
- Cadastro de clientes (CPF ou CNPJ), validação externa de CPF/CNPJ, busca por documento e listagem

> **Nota:** Se o container Docker `app` estiver rodando na porta 8000, `http://localhost:8000` pode responder pelo Docker (sem o painel `/app/`). Pare o container com `docker compose stop app` ou use a API Docker em http://localhost:8001.

## Fluxos principais

1. Cadastrar cliente, veículo, serviços e produtos
2. Criar orçamento com linhas de serviço/produto
3. Enviar orçamento por email (aprovação/recusa via link público)
4. OS gerada automaticamente na aprovação
5. Atribuir mecânico, reservar peças, executar serviço
6. Gerar fatura e registrar pagamento → OS entregue

## Testes

```bash
poetry run pytest --cov=src --cov-report=term-missing
```

## Segurança

Relatório de vulnerabilidades em `docs/security-report.md` (Bandit + pip-audit).

## Requisitos funcionais

Implementação cobre RF01–RF40 conforme plano de tarefas do projeto.
