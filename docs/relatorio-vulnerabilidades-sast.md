# Relatório de Vulnerabilidade de Segurança (SAST)

**Projeto:** Oficina Mecânica API — auto-shop-system  
**Stack:** Python 3.12 · FastAPI · SQLAlchemy · JWT em cookies HttpOnly · Angular

> Atualização: o relatório histórico abaixo foi complementado pelas migrations
> 010/011. O contrato vigente usa cookies de sessão, decisões públicas POST,
> fingerprints HMAC e histórico de transições; referências a Bearer, tokens
> brutos e endpoints GET são achados anteriores à implementação do hardening.
**Referência:** PR #26 — `fix/vulnerability-issues`  
**Commit analisado:** `491ef7433034a46352a1928967b02e7d0d76daef`  
**Data da revisão:** 30/06/2026  
**Ferramentas:** Bandit 1.9.4 · pip-audit 2.10 · `scripts/check_unsafe_defaults.py` · revisão manual  

---

## 1. Sumário Executivo

Este relatório consolida o **scan SAST original** (baseline em `main` antes do hardening) e a **revisão pós-remediação** do PR #26, validada até o commit `491ef74`.

### Baseline (antes do PR #26)

| Fonte | Resultado |
|-------|-----------|
| Bandit (`src/`) | 0 findings automáticos |
| Revisão manual | **11 achados** (4 Alta · 4 Média · 3 Baixa) |
| pip-audit | Sem CVEs conhecidas nas dependências |

### Situação após PR #26 (`491ef74`)

| Fonte | Resultado |
|-------|-----------|
| Bandit (`src/`, 6.428 LOC) | **0 Alta / 0 Média / 1 Baixa** (falso positivo — ver Anexo C) |
| pip-audit | **0 vulnerabilidades** em dependências auditadas |
| `check_unsafe_defaults.py` | **Passou** — sem padrões proibidos em `.env.example`, `docker-compose.yml`, `config.py` |
| Revisão manual pós-fix | **9 de 11 achados corrigidos** · **2 residuais aceitos/documentados** |

### Resumo de remediação

| Severidade original | Total | Corrigido | Residual |
|-------------------|-------|-----------|----------|
| **Alta** | 4 | **4** | 0 |
| **Média** | 4 | **4** | 0 |
| **Baixa** | 3 | **3** | 0 |
| **Total** | 11 | **11** | 0 |

**Conclusão:** o PR #26 endereça todos os riscos **críticos** identificados no scan inicial. O sistema está **apto para homologação** com configuração correta de variáveis de ambiente. Para produção, permanece a recomendação de um limitador distribuído na borda.

---

## 2. Mapa de Remediação — PR #26

| ID | CWE / Achado | Severidade | Status | Commit / evidência |
|----|--------------|------------|--------|-------------------|
| VULN-01 | CWE-798 — Admin default `admin123` automático | Alta | **Corrigido** | `0260cab` — removido seed automático no lifespan; `seed_dev_admin.py` exige `DEV_ADMIN_PASSWORD` |
| VULN-02 | CWE-798/321 — `SECRET_KEY` previsível | Alta | **Corrigido** | `0260cab`, `491ef74` — `SecretStr`, mín. 32 chars, blocklist de valores inseguros |
| VULN-03 | CWE-352 — CSRF em `GET /approve` | Alta | **Corrigido** | Hardening 010/011 — `POST /public/budgets/decisions` com token no corpo + confirmação no Angular |
| VULN-04 | CWE-613 — Token de aprovação sem `exp` | Alta | **Corrigido** | `79a5be9` — `BUDGET_APPROVAL_TOKEN_EXPIRE_HOURS` (default 72h) + `validate_approval_token()` |
| VULN-05 | CWE-200 — Lookup público por documento | Média | **Corrigido** | `de5343a` — `POST /customers/lookup` com segundo fator (email, phone ou placa) |
| VULN-06 | CWE-307 — Sem rate limiting | Média | **Corrigida** | Throttle por IP/usuário com janela, bloqueio e limite de cardinalidade em `src/api/rate_limit.py` |
| VULN-07 | CWE-319 — SMTP sem TLS | Média | **Corrigido** | `de5343a`, `c88c26f` — `SMTP_USE_TLS` / `SMTP_STARTTLS`; obrigatório em `APP_ENV=production\|staging` |
| VULN-08 | CWE-287 — Rastreio OS por ID + documento | Média | **Corrigido** | Hardening 010/011 — `POST /public/service-orders/track` com token no corpo, HMAC e expiração |
| VULN-09 | CWE-942 — CORS hardcoded | Baixa | **Corrigido** | `de5343a` — `CORS_ALLOWED_ORIGINS` via env; validação anti-wildcard com credentials |
| VULN-10 | CWE-693 — Security headers ausentes | Baixa | **Corrigido** | `de5343a` — middleware `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`, HSTS opcional |
| VULN-11 | CWE-798 — Credenciais DB no compose | Baixa | **Corrigido** | `491ef74` — `${POSTGRES_USER:?}` / `${POSTGRES_PASSWORD:?}` / `${SECRET_KEY:?}` |

---

## 3. Análise Detalhada — Achados Corrigidos

### VULN-01 — Credenciais admin automáticas ✅

**Antes:** `AuthService.ensure_default_admin()` criava `admin/admin123` na subida da API.

**Depois (`491ef74`):**
- Lifespan **não** cria usuário admin.
- Seed explícito e opt-in:

```bash
DEV_ADMIN_PASSWORD=<senha-forte> poetry run python -m src.scripts.seed_dev_admin
```

**Arquivos:** `src/application/services/auth_service.py`, `src/scripts/seed_dev_admin.py`, `src/main.py`

---

### VULN-02 — SECRET_KEY previsível ✅

**Antes:** default `"dev-secret-key"` em `config.py` e `docker-compose.yml`.

**Depois:**
- `secret_key: SecretStr = Field(..., min_length=32)` — **obrigatório** via env.
- Blocklist rejeita valores conhecidos (`dev-secret-key`, `change-me`, placeholders do `.env.example`).
- `settings.jwt_secret()` usado em JWT admin e tokens de aprovação/rastreio.

**Arquivos:** `src/config.py`, `.env.example`, `docker-compose.yml`, `scripts/check_unsafe_defaults.py`

---

### VULN-03 — CSRF na aprovação de orçamento ✅

**Antes:** `GET /api/v1/public/budgets/{token}/approve` executava ação de estado.

**Depois:**
- API: **`POST`** `/api/v1/public/budgets/decisions`, com `{token, decision}` no corpo.
- E-mail aponta para frontend com token no fragmento: `/budget-approval?action=approve#...`.
- Componente Angular exige **seleção explícita + botão Confirmar** antes do POST.

**Arquivos:** `src/api/routers/budgets.py`, `src/infrastructure/budget_approval.py`, `frontend/.../budget-approval.component.ts`

---

### VULN-04 — Token de aprovação sem expiração ✅

**Antes:** JWT emitido sem claim `exp`.

**Depois:**

```python
# src/infrastructure/auth/tokens.py
expire = datetime.now(timezone.utc) + timedelta(hours=settings.budget_approval_token_expire_hours)
payload = {"budget_id": budget_id, "type": "budget_approval", "exp": expire}
```

Validação em `validate_approval_token()` rejeita tokens sem `exp` ou com assinatura inválida. Mensagem genérica: `"Orçamento inválido ou expirado"`.

**Testes:** `tests/unit/auth/test_approval_tokens.py`

---

### VULN-05 — Exposição via lookup público de clientes ✅

**Antes:** `GET /customers/by-document/{doc}` retornava dados com CPF/CNPJ sozinho.

**Depois:** `POST /customers/lookup` exige documento **+** segundo fator:
- e-mail cadastrado, **ou**
- telefone cadastrado, **ou**
- placa de veículo do cliente.

Resposta de erro sempre genérica (`404` — `"Cliente não encontrado"`) para evitar enumeração.

**Arquivos:** `src/application/services/customer_public_lookup_service.py`, `src/api/routers/public_customers.py`

---

### VULN-07 — SMTP sem TLS ✅

**Antes:** `start_tls=False` fixo.

**Depois:**
- Flags configuráveis: `SMTP_USE_TLS`, `SMTP_STARTTLS`, `SMTP_REQUIRE_TLS`.
- Em `APP_ENV=production|staging`: TLS **obrigatório** (`model_validator` em `Settings`).
- Falhas SMTP propagadas como `ServiceUnavailableError` (503).

**Arquivos:** `src/config.py`, `src/infrastructure/email/service.py`  
**Testes:** `tests/unit/infrastructure/test_email_service.py`

---

### VULN-08 — Rastreio de OS previsível ✅

**Antes:** `GET /public/service-orders/{id}?document=...` — ID sequencial + CPF.

**Depois:**
- Token opaco (`secrets.token_urlsafe(32)`) enviado por e-mail/PDF.
- Apenas **hash HMAC-SHA256** persistido no banco (`tracking_token_hash`).
- Rota pública vigente: `POST /api/v1/public/service-orders/track` com token no corpo.

**Arquivos:** `src/infrastructure/auth/service_order_tracking.py`, migration `008_service_order_tracking_token_hash.py`, `src/application/services/service_order_email_service.py`

---

### VULN-09 / VULN-10 / VULN-11 — Infraestrutura ✅

| Controle | Implementação |
|----------|---------------|
| CORS | `CORS_ALLOWED_ORIGINS` (lista separada por vírgula) |
| Security headers | Middleware em `src/main.py` |
| HSTS | `SECURITY_HSTS_ENABLED=true` em produção com HTTPS |
| Docker secrets | Variáveis obrigatórias com sintaxe `${VAR:?mensagem}` |
| CI | `.github/workflows/security.yml` — pytest + bandit + pip-audit + unsafe defaults |

---

## 4. Residuais e hardening recomendado (pós-PR #26)

### RES-01 — Rate limiting distribuído (ex-VULN-06)

| Campo | Valor |
|-------|-------|
| **Severidade** | Média (mitigação adicional) |
| **Status** | Throttle local corrigido; distribuição permanece recomendada |
| **Risco residual** | Contadores não são compartilhados entre workers/instâncias |
| **Recomendação** | Complementar o throttle por processo com rate limit no API Gateway/WAF antes de go-live em produção |

---

### RES-02 — Content-Security-Policy (corrigida)

| Campo | Valor |
|-------|-------|
| **Severidade** | Baixa |
| **Status** | Corrigida por middleware da aplicação |
| **Risco residual** | Nenhum identificado no escopo do relatório |
| **Recomendação** | Revisar a política quando novos recursos externos forem adicionados |

---

## 5. Resultados de Scan — Commit `491ef74`

### Bandit

```
Total lines of code: 6428
High:   0
Medium: 0
Low:    1  (B105 falso positivo — ver Anexo C)
```

### pip-audit

Nenhuma vulnerabilidade conhecida nas dependências instaladas (`docs/pip-audit-report.json`).

### check_unsafe_defaults.py

Verifica ausência de:
- `DEV_ADMIN_PASSWORD=admin123`
- `POSTGRES_PASSWORD: oficina`
- `postgresql://oficina:oficina@`
- `SECRET_KEY=dev-secret-key` / `change-me`

**Status:** ✅ passou no commit `491ef74`.

---

## 6. Configuração Segura — Guia Rápido (pós-PR)

### Variáveis obrigatórias (`.env`)

```env
SECRET_KEY=<mínimo 32 caracteres aleatórios>
POSTGRES_PASSWORD=<senha-local-forte>
DEV_ADMIN_PASSWORD=<senha-admin-local>   # apenas dev; vazio desabilita seed
APP_ENV=development                     # production exige TLS SMTP + INVERTEXTO_API_TOKEN
CORS_ALLOWED_ORIGINS=http://localhost:4200
SECURITY_HSTS_ENABLED=false             # true em produção com HTTPS
```

### Bootstrap local seguro

```bash
cp .env.example .env
# editar SECRET_KEY e DEV_ADMIN_PASSWORD
poetry run alembic upgrade head
DEV_ADMIN_PASSWORD=<senha> poetry run python -m src.scripts.seed_dev_admin
poetry run uvicorn src.main:app --reload
```

### Docker Compose

```bash
export POSTGRES_USER=oficina
export POSTGRES_PASSWORD=<senha-forte>
export POSTGRES_DB=oficina
export SECRET_KEY=<secret-32-chars>
docker compose up --build
```

---

## 7. Superfície de Ataque Pública — Estado Atual

| Rota | Método | Autenticação | Proteção |
|------|--------|--------------|----------|
| `/api/v1/auth/login` | POST | Nenhuma | bcrypt + sessão em cookies + rate limit por IP/usuário |
| `/api/v1/customers/lookup` | POST | Documento + 2º fator | Erro genérico 404 |
| `/api/v1/public/budgets/decisions` | **POST** | JWT assinado + exp, uso único | Confirmação UI Angular |
| `/api/v1/public/service-orders/track` | **POST** | Token opaco (HMAC no DB) + expiração | Sem ID sequencial exposto |

> **Nota:** não existe rota `/users`. Admin = `POST /auth/login`. Clientes = `/admin/customers` (JWT) ou `/customers/lookup` (público com 2FA).

---

## 8. Próximos Passos e Prevenção

### Já implementado no PR #26

- [x] Pipeline `.github/workflows/security.yml` (PR + push main)
- [x] Script `scripts/check_unsafe_defaults.py` no CI
- [x] Testes de configuração: `tests/unit/test_config.py`, `tests/unit/test_seed_dev_admin.py`
- [x] Testes de tokens: `tests/unit/auth/test_approval_tokens.py`
- [x] Documentação atualizada: `README.md`, `.env.example`

### Backlog recomendado

| Prioridade | Ação |
|------------|------|
| P1 | Rate limiting distribuído em login e rotas públicas (RES-01) |
| P3 | Renovar `docs/bandit-report.txt` no CI (artefato gerado automaticamente) |
| P3 | Suprimir/documentar falso positivo B105 com `# nosec B105` + comentário |

### Governança contínua

| Controle | Frequência |
|----------|------------|
| Bandit + pip-audit + unsafe defaults (CI) | Todo PR |
| Rotação `SECRET_KEY` / credenciais SMTP | Trimestral |
| Revisão endpoints públicos | A cada nova feature |
| Pentest manual (aprovação orçamento + rastreio OS) | Antes de go-live |

---

## Anexo A — Commits de segurança (PR #26)

| Commit | Descrição |
|--------|-----------|
| `0260cab` | Harden auth secrets e admin seed |
| `79a5be9` | Secure budget approval flow (POST + exp) |
| `de5343a` | Security hardening base (CORS, headers, SMTP, lookup) |
| `eafde8e` | Confirmação explícita de aprovação no frontend |
| `72be1b3` | Token-based service order tracking |
| `c88c26f` | SMTP delivery failures handling |
| `491ef74` | Remove unsafe defaults do docker-compose |

---

## Anexo B — Comparativo antes / depois (trechos)

### SECRET_KEY

```python
# Antes
secret_key: str = "dev-secret-key"

# Depois (491ef74)
secret_key: SecretStr = Field(..., min_length=32)
# + validator rejeitando placeholders conhecidos
```

### Aprovação de orçamento

```python
# Antes
@public_router.get("/{token}/approve")

# Depois
@public_router.post("/{token}/approve")
# + frontend /budget-approval com confirmação explícita
```

### Rastreio de OS

```python
# Antes
GET /public/service-orders/{id}?document=52998224725

# Depois
POST /public/service-orders/track {"token": "<opaque_token>"}
# token hash armazenado: HMAC-SHA256(secret, token)
```

---

## Anexo C — Falso positivo Bandit (B105)

```
Location: src/application/services/budget_approval_service.py:15
INVALID_APPROVAL_TOKEN_MESSAGE = "Orçamento inválido ou expirado"
```

Bandit classifica como `hardcoded_password_string` por conter a substring `"expirado"`. **Não é credencial.** Ação sugerida: `# nosec B105` com comentário explicativo ou ajuste da mensagem para evitar trigger.

---

**Elaborado por:** Revisão SAST pós-PR #26  
**Classificação:** Interno — Desenvolvimento e Gerência  
**Próxima revisão:** após merge do PR #26 em `main` ou implementação de RES-01 distribuído
