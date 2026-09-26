# Templates CI/CD — ecossistema Auto Shop (#89)

Modelos para repositórios **independentes** (sem checkout cross-repo). Copie o `ci.yml` adequado para `.github/workflows/ci.yml` em cada repositório.

| Repositório | Template | Jobs principais |
|-------------|----------|-----------------|
| Backend (`auto-shop-system`) | Implementado em [../workflows/ci.yml](../workflows/ci.yml) | testes, gateway, manifests, Terraform K8s/AWS, smoke |
| Frontend | [frontend-ci.yml](./frontend-ci.yml) | lint, build, testes unitários |
| Infraestrutura / IaC | [infra-ci.yml](./infra-ci.yml) | `terraform fmt`, `validate`, `plan` (sem app) |
| Gateway / integração | [gateway-ci.yml](./gateway-ci.yml) | testes Lambda, `terraform fmt/validate` em IaC do gateway |

## Tag de artefato (Cenário 5)

Use tag imutável por commit:

```bash
short="${GITHUB_SHA::7}"
IMAGE_REFERENCE="ghcr.io/${GITHUB_REPOSITORY}:sha-${short}"
```

Deploy automático: ver issue **#90** (`cd-staging.yml`, `cd-prod.yml`).

## Regras

- Não usar `actions/checkout` de outro repositório.
- `workflow_call` apenas **dentro** do mesmo repo.
- Falha em um repo não cancela pipelines de outros repos.
