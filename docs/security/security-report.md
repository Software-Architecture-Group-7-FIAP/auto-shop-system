# Security Scan Report — Oficina Mecânica API

> **Relatório completo:** [relatorio-vulnerabilidades-sast.md](./relatorio-vulnerabilidades-sast.md)  
> **Referência:** PR #26 (`fix/vulnerability-issues`) · commit `491ef74` · revisão 30/06/2026

---

## Ferramentas

| Ferramenta | Finalidade |
|------------|------------|
| **Bandit** | SAST — padrões inseguros em Python |
| **pip-audit** | CVEs em dependências |
| **`scripts/check_unsafe_defaults.py`** | Bloqueia segredos/defaults inseguros versionados |
| **CI** | `.github/workflows/security.yml` (pytest + bandit + pip-audit + unsafe defaults) |

---

## Como executar localmente

```bash
poetry run bandit -r src -ll -f txt -o docs/bandit-report.txt
poetry run pip-audit -f json -o docs/pip-audit-report.json
poetry run python scripts/check_unsafe_defaults.py
poetry run pytest
```

---

## Resultado do scan (pós PR #26)

| Verificação | Status | Observação |
|-------------|--------|------------|
| Bandit (`src/`) | ✅ Passou | 0 Alta / 0 Média / 1 Baixa (falso positivo B105) |
| pip-audit | ✅ Passou | 0 vulnerabilidades conhecidas |
| Unsafe defaults | ✅ Passou | Sem `admin123`, `dev-secret-key`, `oficina/oficina` versionados |
| SQL injection | ✅ Mitigado | SQLAlchemy ORM — queries parametrizadas |
| Autenticação admin | ✅ Implementado | JWT em `/api/v1/admin/*`; admin via seed explícito |
| `SECRET_KEY` | ✅ Corrigido | `SecretStr` obrigatório (≥ 32 chars), blocklist de placeholders |
| Aprovação de orçamento | ✅ Corrigido | `POST` + token com `exp` + confirmação no Angular |
| Lookup público de clientes | ✅ Corrigido | `POST /customers/lookup` com segundo fator |
| Rastreio de OS | ✅ Corrigido | Token opaco — `GET /public/service-orders/track/{token}` |
| SMTP | ✅ Corrigido | TLS configurável; obrigatório em `production`/`staging` |
| CORS / headers | ✅ Corrigido | Origens via env; middleware de security headers |
| Rate limiting | ⚠️ Backlog | Removido do MVP — ver RES-01 no relatório completo |
| Content-Security-Policy | ⚠️ Backlog | Parcialmente mitigado — ver RES-02 no relatório completo |

**Remediação:** 9 de 11 achados corrigidos · 2 residuais documentados (rate limiting, CSP).

---

## Bootstrap seguro (desenvolvimento)

```bash
cp .env.example .env
# Defina SECRET_KEY (≥ 32 caracteres aleatórios) e DEV_ADMIN_PASSWORD
poetry run alembic upgrade head
DEV_ADMIN_PASSWORD=<senha-forte> poetry run python -m src.scripts.seed_dev_admin
poetry run uvicorn src.main:app --reload
```

Com Docker Compose, exporte antes de subir:

```bash
export POSTGRES_USER=oficina
export POSTGRES_PASSWORD=<senha-forte>
export POSTGRES_DB=oficina
export SECRET_KEY=<secret-32-chars>
docker compose up --build
```

---

## Recomendações para produção

1. Definir `APP_ENV=production` (ativa validações de TLS SMTP e token Invertexto).
2. Habilitar HTTPS e `SECURITY_HSTS_ENABLED=true`.
3. Rotacionar `SECRET_KEY` e credenciais SMTP via secrets manager.
4. Implementar rate limiting (login + rotas públicas) — backlog RES-01.
5. Adicionar Content-Security-Policy no reverse proxy — backlog RES-02.
6. Manter CI de segurança obrigatório em todo merge request.

Detalhes técnicos, mapa CWE, comparativos antes/depois e anexos: **[relatorio-vulnerabilidades-sast.md](./relatorio-vulnerabilidades-sast.md)**.
