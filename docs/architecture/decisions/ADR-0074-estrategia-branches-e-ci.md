# ADR-0074: Estratégia de branches, CI e proteção (#89 / #91)

- **Status:** Aceito
- **Data:** 2026-10-23
- **Issues:** [#89 CI multi-repo](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/issues/89), [#91 Branch protection](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/issues/91)

## Contexto

O ecossistema tem quatro repositórios com pipelines independentes. O backend monorepo concentra a maior parte dos jobs de qualidade; merges diretos em `main`/`develop` invalidariam revisão e checks.

## Decisão

### Branches

| Branch | Uso |
| --- | --- |
| `develop` | Integração contínua; deploy staging (CD) quando habilitado |
| `main` | Linha de produção; deploy production após merge controlado |
| Feature branches | `issue-NN-descricao` ou prefixo acordado; PR obrigatório |

Proteção em `main` e `develop` (repo `auto-shop-system`): PR + 1 review + **re-aprovação após push** + checks obrigatórios + assinatura de commit verificada (política org). Script: `scripts/apply_branch_protection.sh` — ver [`.github/BRANCH_PROTECTION.md`](../../../.github/BRANCH_PROTECTION.md).

### CI backend (`ci.yml`)

Jobs obrigatórios no merge:

- `test-and-security` (pytest, Bandit, pip-audit)
- `gateway` (smoke do gateway local)
- `manifests` (Docker Compose + imagem)
- `terraform-k8s` / `terraform-aws` (fmt, validate, plan K8s)
- `cluster-smoke` (Kind + deploy script)
- `frontend` (lint/build Angular)

Workflow **não** roda deploy; CD está em `cd-staging.yml` / `cd-prod.yml` ([`.github/CD.md`](../../../.github/CD.md)).

### CI nos demais repositórios

Templates em [`.github/ecosystem-templates/`](../../../.github/ecosystem-templates/README.md) — copiar para cada repo **sem** checkout cross-repo.

| Repo | Template |
| --- | --- |
| `lambda-auth` | `gateway-ci.yml` |
| `database-infra` / `k8s-infra` | `infra-ci.yml` |

Falha em um repositório não cancela pipelines dos outros.

### Autenticação de deploy (#90)

- Build/push: `GITHUB_TOKEN` → private GHCR, tag `sha-<7 chars>`.
- Deploy: GitHub Actions reads GHCR with a read-only `GITHUB_TOKEN`, verifies the commit label, and mirrors the immutable image into private ECR through OIDC. EKS nodes pull from ECR using their AWS identity; no long-lived GHCR token or Kubernetes pull secret is stored.
- Deploy K8s: OIDC → role AWS por Environment (`staging` / `production`).
- Gate: `DEPLOY_STAGING_ENABLED` / `DEPLOY_PRODUCTION_ENABLED` até cluster staging (#87) existir.

## Consequências

- ADRs e RFCs referenciam `develop` como base de PR.
- Alterar jobs obrigatórios exige atualizar branch protection e o script #91.
- OIDC vs access keys: deploy usa **OIDC**; segredos de app permanecem no cluster/Secrets Manager, não no Git.
