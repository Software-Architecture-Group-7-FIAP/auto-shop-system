# Oficina Mecânica — Sistema Integrado de Atendimento

Backend monolítico FastAPI para gestão de ordens de serviço (OS), clientes, veículos, peças/insumos e faturamento.

**FIAP 15SOAT — Tech Challenge Fase 1 (T01 Bootstrap)**

## Stack

- Python 3.12 + FastAPI
- PostgreSQL 16
- SQLAlchemy 2 + Alembic
- Docker + docker-compose

### Por que PostgreSQL?

PostgreSQL foi escolhido como banco de dados relacional por:

- **Transações ACID** — fluxos de orçamento e OS exigem consistência (reservas de estoque, aprovações, faturamento).
- **Integridade referencial** — chaves estrangeiras garantem vínculos corretos entre clientes, veículos, orçamentos e ordens de serviço.
- **Escalabilidade e maturidade** — suporte robusto a índices, JSON, concorrência e ecossistema maduro para evolução do monolito.

## Arquitetura

Monolito em camadas:

```
src/
  domain/         # regras de negócio, exceções de domínio
  application/    # casos de uso / services (T02+)
  infrastructure/ # banco de dados, integrações externas
  api/            # factory FastAPI, rotas e handlers
```

A aplicação é criada via factory `create_app()` em `src/api/factory.py`, expondo health check, Swagger e handler global de erros de domínio.

## Executar com Docker

```bash
docker compose up --build
```

- API: http://localhost:8000
- Swagger: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Health check

```bash
curl http://localhost:8000/health
```

Resposta esperada:

```json
{"status": "ok", "database": "connected"}
```

## Executar localmente

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/macOS
pip install -r requirements.txt
copy .env.example .env        # Windows
# cp .env.example .env        # Linux/macOS
```

Subir PostgreSQL local (ou ajustar `DATABASE_URL` no `.env`), depois:

```bash
alembic upgrade head
uvicorn src.main:app --reload
```

## Testes

```bash
pytest
```

## Próximas tarefas

A T01 entrega apenas a infraestrutura base. Funcionalidades de negócio (clientes, veículos, orçamentos, etc.) serão adicionadas nas tarefas T02 em diante.
