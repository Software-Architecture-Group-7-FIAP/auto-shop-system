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
docker compose up --build
```

- API: http://localhost:8000
- Swagger: http://localhost:8000/docs
- MailHog UI: http://localhost:8025

## Executar localmente

Instale o [Poetry](https://python-poetry.org/docs/#installation) e depois:

```bash
poetry install
cp .env.example .env
# Subir o banco: docker compose up db -d  (ou PostgreSQL local)
# DATABASE_URL usa localhost fora do Docker; dentro do Compose use host db
poetry run alembic upgrade head
poetry run uvicorn src.main:app --reload
```

## Autenticação

Login admin padrão (criado automaticamente):

- **Usuário:** `admin`
- **Senha:** `admin123`

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'
```

Use o token JWT retornado no header `Authorization: Bearer <token>` para rotas `/api/v1/admin/*`.

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
