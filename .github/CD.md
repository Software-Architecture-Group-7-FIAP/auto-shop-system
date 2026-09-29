# CD — build/push, OIDC e deploy (#90)

Fluxo alinhado à fase operacional:

```text
PR → ci.yml (testes + segurança) → merge em develop → cd-staging.yml
merge develop → main (fim da fase) → cd-prod.yml
```

## Cenário 1 — validação em PR

O workflow [`ci.yml`](./workflows/ci.yml) roda em todo PR para `develop` ou `main`.  
A obrigatoriedade antes do merge é configurada na issue **#91** (branch protection + required checks).

## Cenário 2 — build e push (GHCR)

Após merge:

| Branch | Workflow | Registry |
|--------|----------|----------|
| `develop` | `cd-staging.yml` | `ghcr.io/<org>/<repo>:sha-<7 chars>` |
| `main` | `cd-prod.yml` | idem |

Autenticação no GHCR: `GITHUB_TOKEN` com `packages: write` (sem access key AWS).

## Cenários 3–4 — deploy Kubernetes

Deploy usa [`k8s/scripts/deploy.sh`](../k8s/scripts/deploy.sh) (foundation → migration → app → ingress + smoke).

**Enquanto o staging (#87) não estiver pronto**, o job de deploy fica **desligado** por padrão (`DEPLOY_ENABLED` ≠ `true`).  
O job `deploy-*-skipped` ainda publica a imagem e imprime instruções.

### Habilitar deploy

1. Criar **GitHub Environments** `staging` e `production`.
2. Em **production**, marcar **Required reviewers** (≥ 1).
3. Definir **Variables** (por environment ou repositório):

| Variable | Exemplo | Uso |
|----------|---------|-----|
| `DEPLOY_ENABLED` | `true` | Liga jobs de deploy |
| `AWS_REGION` | `us-east-1` | Região EKS |
| `EKS_CLUSTER_NAME` | `auto-shop-staging` | Cluster alvo |

4. Definir **Secret** por environment:

| Secret | Descrição |
|--------|-----------|
| `AWS_DEPLOY_ROLE_ARN` | Role IAM assumida via OIDC (`id-token: write`) |

5. Garantir no cluster: Secret `auto-shop-secrets`, TLS e RBAC para a role (issue **#82** / **#87**).

### Produção

- Estratégia: **rolling** via `Deployment` + Job de migration versionado por imagem (documentado em [`docs/deployment.md`](../docs/deployment.md)).
- **Rollback:** redeploy com tag `sha-<commit anterior>` (mesmo script).

## Cenário 5 — OIDC AWS

Terraform opcional em [`infra/aws/github_oidc.tf`](../infra/aws/github_oidc.tf):

```bash
terraform -chdir=infra/aws apply \
  -var=enable_github_oidc=true \
  -var=github_repository=Software-Architecture-Group-7-FIAP/auto-shop-system \
  # ... demais vars do módulo AWS
```

Outputs: `github_deploy_role_arn_staging`, `github_deploy_role_arn_production` → copiar para secrets do GitHub.

A role criada inclui `eks:DescribeCluster`; **acesso de API ao EKS** (access entry / `aws-auth`) deve ser provisionado pelo repo de infra (**#72**, **#82**).

## Cenário 6 — checklist GitHub Settings

- [ ] Environment `staging` com vars/secrets acima
- [ ] Environment `production` com approval + vars/secrets
- [ ] Pacote GHCR visível para o org (Settings → Actions → General → Workflow permissions: read/write)

## Referências

- Issue [#90](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/issues/90)
- Plano integrado [#98](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/issues/98)
