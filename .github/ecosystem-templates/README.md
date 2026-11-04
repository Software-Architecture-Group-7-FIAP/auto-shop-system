# Templates CI/CD — ecossistema Auto Shop (#89)

Modelos para repositórios **independentes** (sem checkout cross-repo). Copie o `ci.yml` adequado para `.github/workflows/ci.yml` em cada repositório.

| Repositório | Template | Jobs principais |
|-------------|----------|-----------------|
| Backend (`auto-shop-system`) | Implementado em [../workflows/ci.yml](../workflows/ci.yml) | testes, gateway, manifests, Terraform K8s/AWS, smoke |
| Frontend | [frontend-ci.yml](./frontend-ci.yml) | lint, build, testes unitários |
| Infraestrutura / IaC | [infra-ci.yml](./infra-ci.yml) | `fmt` e `validate` em pull request, sem credencial AWS; `plan` só no push de `main`/`develop`, via OIDC no environment `aws-plan` (`AWS_PLAN_ROLE_ARN`) |
| Gateway / integração | [gateway-ci.yml](./gateway-ci.yml) | testes Lambda via `requirements.txt` ([partida](./gateway-requirements.txt): `pytest` e `PyJWT`), `terraform fmt/validate` |

### Implementação nos quatro repositórios ([#89](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/issues/89))

| Repositório | Cenário #89 | CI | CD / deploy |
| --- | --- | --- | --- |
| [auto-shop-system](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system) | 1 (backend) + 2 (frontend no monorepo) | [`.github/workflows/ci.yml`](../workflows/ci.yml) | [cd-staging.yml](../workflows/cd-staging.yml), [cd-prod.yml](../workflows/cd-prod.yml) ([#90](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/issues/90)) |
| [lambda-auth](https://github.com/Software-Architecture-Group-7-FIAP/lambda-auth) | 4 (gateway) | [`ci.yml`](https://github.com/Software-Architecture-Group-7-FIAP/lambda-auth/blob/main/.github/workflows/ci.yml) | Terraform manual / apply fora do PR |
| [database-infra](https://github.com/Software-Architecture-Group-7-FIAP/database-infra) | 3 (IaC) | [`ci.yml`](https://github.com/Software-Architecture-Group-7-FIAP/database-infra/blob/main/.github/workflows/ci.yml) | [`apply.yml`](https://github.com/Software-Architecture-Group-7-FIAP/database-infra/blob/main/.github/workflows/apply.yml) (`STAGING_ACTIVE`) |
| [k8s-infra](https://github.com/Software-Architecture-Group-7-FIAP/k8s-infra) | 3 (IaC) | [`ci.yml`](https://github.com/Software-Architecture-Group-7-FIAP/k8s-infra/blob/main/.github/workflows/ci.yml) | [`apply.yml`](https://github.com/Software-Architecture-Group-7-FIAP/k8s-infra/blob/main/.github/workflows/apply.yml) (`STAGING_ACTIVE`) |

Artefato imutável por commit (cenário 5): imagem `ghcr.io/...:sha-<7>` no backend; `dist/lambda-auth.zip` no job de CI do `lambda-auth`.

## Tag de artefato (Cenário 5)

Use tag imutável por commit:

```bash
short="${GITHUB_SHA::7}"
IMAGE_REFERENCE="ghcr.io/${GITHUB_REPOSITORY}:sha-${short}"
```

Deploy automático (#90): [`../workflows/cd-staging.yml`](../workflows/cd-staging.yml), [`cd-prod.yml`](../workflows/cd-prod.yml), [`reusable-build-push.yml`](../workflows/reusable-build-push.yml). Configuração: [`../CD.md`](../CD.md).

## Regras

- Não usar `actions/checkout` de outro repositório.
- `workflow_call` apenas **dentro** do mesmo repo.
- Falha em um repo não cancela pipelines de outros repos.
