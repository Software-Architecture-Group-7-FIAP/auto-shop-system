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

**Enquanto o staging (#87) não estiver pronto**, o deploy fica **desligado**. O gate é variável de **repositório**, porque o `if` do job roda antes de entrar no Environment. O job `deploy-*-skipped` ainda publica a imagem e imprime instruções.

### Habilitar deploy

1. Criar **GitHub Environments** `staging` e `production`.
2. Em **Deployment branches and tags**:
   - `staging`: apenas `develop`
   - `production`: apenas `main`
3. Em **production**, marcar **Required reviewers** (≥ 1).
4. Variáveis de **repositório** (ligam o job; não coloque o gate no Environment):

| Variable | Exemplo | Uso |
|----------|---------|-----|
| `DEPLOY_STAGING_ENABLED` | `true` | Liga o deploy no push de `develop` |
| `DEPLOY_PRODUCTION_ENABLED` | `true` | Liga o deploy no push de `main` |

5. Variáveis de **Environment** (lidas depois que o job entra nele):

| Variable | Exemplo | Uso |
|----------|---------|-----|
| `AWS_REGION` | `us-east-1` | Região EKS |
| `EKS_CLUSTER_NAME` | `auto-shop-staging` | Cluster alvo |

6. **Secret** por environment:

| Secret | Descrição |
|--------|-----------|
| `AWS_DEPLOY_ROLE_ARN` | Role IAM assumida via OIDC (`id-token: write`) |

7. No GHCR, deixar o pacote **público** antes de ligar o deploy. A imagem nasce privada e os manifests não têm `imagePullSecrets`; sem visibilidade pública o kubelet fica em `ImagePullBackOff`.
8. Garantir no cluster: Secret `auto-shop-secrets`, TLS e RBAC para a role (issue **#82** / **#87**).

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

A trust policy restringe o subject a `repo:<org>/<repo>:environment:staging` ou `production`. Esse token não inclui a branch. A limitação de branch fica na regra de deployment do Environment (`develop` em staging, `main` em production). A role inclui `eks:DescribeCluster`; **acesso de API ao EKS** (access entry / `aws-auth`) deve ser provisionado pelo repo de infra (**#72**, **#82**).

## Cenário 6 — checklist GitHub Settings

- [ ] Environment `staging`: deployment branch só `develop`, vars `EKS_CLUSTER_NAME` e `AWS_REGION`, secret `AWS_DEPLOY_ROLE_ARN`
- [ ] Environment `production`: deployment branch só `main`, required reviewers, vars e secret equivalentes
- [ ] Variáveis de repositório `DEPLOY_STAGING_ENABLED` e `DEPLOY_PRODUCTION_ENABLED` (o `if` do workflow não lê variável de Environment)
- [ ] Pacote GHCR **público** antes de ligar o deploy
- [ ] Workflow permissions: read and write (Settings → Actions → General), para o `GITHUB_TOKEN` publicar no GHCR

## Referências

- Issue [#90](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/issues/90)
- Plano integrado [#98](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/issues/98)
