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
| Autenticação admin | ✅ Implementado | Access JWT de 15 min em cookie HttpOnly, refresh opaco rotativo e CSRF; admin via seed explícito |
| `SECRET_KEY` | ✅ Corrigido | `SecretStr` obrigatório (≥ 32 chars), blocklist de placeholders |
| Aprovação de orçamento | ✅ Corrigido | `POST /public/budgets/decisions`, fingerprint HMAC, expiração, uso idempotente e link em fragmento |
| Lookup público de clientes | ✅ Corrigido | `POST /customers/lookup` com segundo fator |
| Rastreio de OS | ✅ Corrigido | `POST /public/service-orders/track`, fingerprint HMAC, revogação no reenvio e expiração pós-entrega |
| SMTP | ✅ Corrigido | TLS configurável; obrigatório em `production`/`staging` |
| CORS / headers | ✅ Corrigido | Origens via env; middleware de security headers |
| Rate limiting | ✅ Corrigido | Throttle por IP e por usuário em `POST /auth/login` (`src/api/rate_limit.py`) |
| Content-Security-Policy | ✅ Corrigido | Enviado pelo middleware de security headers; `/docs` e `/redoc` isentos (assets em CDN) |
| CSRF | ✅ Corrigido | Double-submit + checagem de `Origin` em toda requisição que altera estado |

**Remediação:** os achados de estados, tokens, PII e sessão foram encerrados nas migrations 010/011. Rate limiting e CSP foram implementados na aplicação.

O painel Angular deixou de usar `alert()` global: erros agora vão para um stack de notificações in-app (`NotificationService` + `app-notifications`), com `role="alert"`, dispensa manual, expiração automática e deduplicação — item 10 do hardening review encerrado.

O rate limiting é **por processo** e mantém um limite de cardinalidade para os
baldes (`LOGIN_RATE_LIMIT_MAX_BUCKETS`). Com mais de um worker cada um mantém
seus próprios contadores; para produção, complementar com um limitador na
borda (reverse proxy / WAF).

---

## Runbook de upgrade — migration 011 (obrigatório)

A migration 011 adiciona `users.role` com default **OPERATOR** e **rebaixa todos os usuários existentes**. Isso é deliberado: nenhuma migration concede papel administrativo implicitamente. Sem o passo abaixo, ninguém consegue usar `PATCH /admin/service-orders/{id}/status-override`, e não existe tela para corrigir isso pela aplicação.

```bash
poetry run alembic upgrade head
# Promova exatamente um administrador logo em seguida:
poetry run python -m src.scripts.promote_first_admin
```

Verificação:

```sql
SELECT username, role FROM users ORDER BY id;
```

O passo de promoção só é necessário em bases **já existentes**. Em instalação nova, `seed_dev_admin` já cria o primeiro usuário como `ADMIN`.

Validado em 2026-08-21 contra `postgres:16-alpine`: base pré-011 com dois usuários → `alembic upgrade head` → ambos em `OPERATOR` → `promote_first_admin` promove o primeiro.

A migration 010 é **forward-only**: o PostgreSQL não remove valores de enum já adicionados, e o `downgrade()` não remapeia linhas gravadas como `Substituído` / `Aguardando início`. Rollback se faz por restauração de backup, não por `alembic downgrade`.

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
4. Complementar o rate limiting da aplicação com um limitador distribuído na borda (o atual é por processo).
5. Executar `promote_first_admin` logo após `alembic upgrade head` (ver runbook acima).
6. Manter CI de segurança obrigatório em todo merge request.

Detalhes técnicos, mapa CWE, comparativos antes/depois e anexos: **[relatorio-vulnerabilidades-sast.md](./relatorio-vulnerabilidades-sast.md)**.
