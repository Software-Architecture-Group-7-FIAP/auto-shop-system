# Security Scan Report — Oficina Mecânica API

## Tools

- **Bandit** — static analysis for common Python security issues
- **pip-audit** — dependency vulnerability scan

## How to run

```bash
poetry run bandit -r src -f txt -o docs/bandit-report.txt
poetry run pip-audit -f json -o docs/pip-audit-report.json
```

## Summary

| Check | Status | Notes |
|-------|--------|-------|
| Hardcoded secrets | Mitigated | `SECRET_KEY` via environment variable |
| SQL injection | Mitigated | SQLAlchemy ORM with parameterized queries |
| Authentication | Implemented | JWT on `/api/v1/admin/*` routes |
| Input validation | Implemented | CPF/CNPJ and plate validators in domain layer |
| Public endpoints | Scoped | Budget approval tokens and OS tracking by document |

## Recommendations for production

1. Rotate `SECRET_KEY` and use a secrets manager
2. Enable HTTPS/TLS
3. Rate-limit public approval and tracking endpoints
4. Use real SMTP with TLS for email delivery
5. Restrict CORS to known front-end origins
