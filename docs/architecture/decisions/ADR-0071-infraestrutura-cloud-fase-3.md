# ADR-0071: Infraestrutura cloud — Fase 3 operacional

- **Status:** Aceito (documentação); implantação staging/produção pendente (#87)
- **Data:** 2026-10-23
- **Issue de referência:** [#95 — Documentação de arquitetura](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/issues/95)
- **Relacionado:** [#88 API Gateway](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/issues/88), [#89 CI](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/issues/89), [#90 CD](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/issues/90)

## Contexto

A Fase 3 exige borda pública na AWS, pipelines independentes por repositório, Kubernetes para a aplicação e segregação de segredos. O monorepo `auto-shop-system` concentra backend FastAPI, frontend Angular e manifests/Terraform de app; Lambdas, banco gerenciado e cluster compartilham fronteiras documentadas neste ADR.

## Repositórios do ecossistema

| Repositório | Conteúdo | Dono operacional (FIAP) |
| --- | --- | --- |
| `auto-shop-system` | Backend, `frontend/`, `k8s/`, `infra/` (app no cluster), templates CI/CD | Suelen (#88–#95) |
| `lambda-auth` | Lambdas de login admin/gateway e identidade de cliente (CPF/JWKS) | Gustavo (#63–#68) |
| `database-infra` | RDS PostgreSQL, rede, papéis de banco, snapshots | Gustavo (#69–#87) |
| `k8s-infra` | Cluster EKS, VPC Link, ALB interno, integração com Gateway | Gustavo (#69–#87) |

Não há repositório frontend separado: o painel Angular vive em `auto-shop-system/frontend/`.

## Topologia de borda (staging e produção)

Fluxo alvo documentado nos runbooks e no diagrama [`fase-operacional.mmd`](../fase-operacional.mmd):

```text
Cliente / Admin
    → Route53 (opcional)
    → API Gateway REST (regional)
    → AWS WAF (rate limit + regras gerenciadas)
    → Destino por rota:
         • Lambda (proxy): login gateway, token cliente, JWKS
         • HTTP(S) proxy / VPC Link v2 → ALB interno → Ingress → Service → Pods FastAPI
    → Observabilidade: logs JSON (app), access logs Gateway, APM (#92–#94)
```

Ambientes **staging** e **production** usam a mesma forma, com namespaces, hosts, secrets e ARNs distintos. Valores concretos de conta, ARN e segredo ficam fora do Git (GitHub Environments, Secrets Manager, Parameter Store).

## Banco de dados — quatro papéis

| Papel | Uso | Privilégio |
| --- | --- | --- |
| Migração | Job Alembic no deploy | DDL + DML temporário |
| Aplicação | Pods FastAPI | DML conforme domínio |
| Lambda leitura | `POST /auth/customer/token` | `SELECT` mínimo em `customers` / documentos |
| Operação / backup | Snapshots, restore, suporte | Gerenciado em `database-infra` |

A aplicação permanece dona do schema; Lambdas não executam migrations.

## Segredos e configuração

- **ConfigMap:** URLs públicas, CORS, issuer JWKS, flags não sensíveis.
- **Secret / KMS:** `DATABASE_URL`, peppers JWT admin, SMTP, tokens de integração, chaves privadas de assinatura (Lambda).
- **GitHub:** OIDC para deploy (#90); variáveis `DEPLOY_*_ENABLED` até staging (#87) estar pronto.

Não versionar segredos, CPF, tokens ou evidências com PII em issues, PRs ou diagramas.

## Consequências

- Documentação e ADRs usam `docs/architecture/decisions/` (não `docs/adr/` solto).
- Homologação integrada (#68) depende de #87 + configuração Gateway/Lambda alinhada ao [ADR-0064](./ADR-0064-autenticacao-cliente-cpf-jwt.md) e ao runbook [`lambda-homologation.md`](../../validation/lambda-homologation.md).
- Teardown e snapshots seguem política acadêmica definida em `database-infra` (fora deste repo).

## Histórico

| Data | Nota |
| --- | --- |
| 2026-10-23 | ADR criado na fatia 1 da #95; prevalece sobre notas conflitantes da issue que citem quatro repos com frontend separado. |
