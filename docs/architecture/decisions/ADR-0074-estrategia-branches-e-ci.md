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

- Build/push: `GITHUB_TOKEN` → public GHCR, immutable tag `sha-<7 chars>`.
- Deploy: before AWS authentication, GitHub Actions verifies anonymous GHCR access and deploys the same immutable image directly. EKS pulls from public GHCR; the deploy job needs no `packages: read`, ECR mirror, registry credential, or Kubernetes pull secret.
- Existing ECR images are legacy artifacts and remain untouched until a separate retention review.
- Deploy K8s: OIDC → role AWS por Environment (`staging` / `production`).
- Gate: `DEPLOY_STAGING_ENABLED` / `DEPLOY_PRODUCTION_ENABLED` até cluster staging (#87) existir.

### Atualização de distribuição de imagens (2026-11-01)

A estratégia de registry desta ADR foi supersedida pela [ADR-0079](ADR-0079-registry-privado-ecr.md): o GHCR autenticado permanece como origem de build, e os deploy jobs autorizados espelham a imagem imutável para o ECR privado antes de atualizar o EKS. A role OIDC do deploy precisa de permissões ECR limitadas ao repositório esperado, e os nós EKS precisam de permissões de pull.

## Consequências

- ADRs e RFCs referenciam `develop` como base de PR.
- Alterar jobs obrigatórios exige atualizar branch protection e o script #91.
- OIDC vs access keys: deploy usa **OIDC**; segredos de app permanecem no cluster/Secrets Manager, não no Git.
