# Application deploy and environment lifecycle

## Lifecycle coordinator

`.github/workflows/environment-start.yml` is the only environment opening clock. PRD opens at 06:00 BRT on 1-5 November 2026. `.github/workflows/environment-stop.yml` closes PRD at 22:00 BRT on 1-5 November. `.github/workflows/environment-health.yml` has no schedule; the opener dispatches its 06:45 BRT check and waits for a correlated run. The public API Gateway and CloudFront URL stays provisioned through the night; maintenance mode disconnects the temporary backend while keeping the URL stable.

HML is manual only through 31 October 2026. Dispatch `environment-start.yml` with `stage=hml`; optionally provide `started_at` in UTC. The default start is 17:00 BRT. A session may start between 07:00 and 17:00 BRT, runs for up to five hours, and is stopped automatically at its calculated end. The coordinator rejects a second HML or PRD opening run on the same BRT date. Re-run the original opening run for recovery; a separate run on the same day is rejected.

The HML close dispatch requires the same `session_id` and `started_at` produced by the opener. PRD close is scheduled and may also be manually dispatched for the current validated session. Both close paths cancel and wait for that session's app deployment, move the public edge to maintenance, destroy the ephemeral database, disable NAT, destroy the platform and compute stacks in order, and preserve the VPC/subnets/SSM contract. The teardown work deadline is 20 minutes before the session-specific cleanup deadline (22:40 BRT for PRD); the five-minute handoff margin protects the independent audit job. The final 15 minutes (22:45–23:00 BRT for PRD) are reserved for the read-only orphan audit. Late close requests skip new teardown work and wait for the reserved audit window. The audit job lists correlated runs in the app, K8s, and database repositories and fails closed if a mutation remains active or GitHub cannot be queried. The K8s audit also shares its `staging-infra` concurrency group with apply/destroy, so Terraform cannot mutate the foundation while the inventory is read. Before database destroy, the coordinator finds apply runs by the exact session title prefix, cancels queued or running matches, and waits for `completed`; multiple active matches fail closed before destroy dispatch.

Opening creates the K8s foundation and platform, bootstraps the synthetic database, dispatches the app workflow, applies database grants after migrations, and reconciles the public edge. Each cross-repository dispatch derives a stable 32-character correlation ID from the central workflow run, attempt, and requested operation, then accepts only the run with that exact `display_title`. A rerun resumes an active or successful correlated run; it creates a new correlation ID only after the prior run failed terminally. Missing, duplicate, failed, or ambiguous runs stop the coordinator. API requests are bounded by the remaining deadline. Teardown work stops at its absolute deadline; the coordinator requests cancellation and waits for at most 30 seconds after its final bounded API calls. If the run remains active or GitHub cannot be reached, teardown reports failure and the audit job blocks the K8s inventory until all correlated mutations are complete. A close checks that the same session had a mutating opening step; absent openings and preflight-only failures are recorded as no-ops.

The audit guard polls every 15 seconds for up to 60 seconds after the reserved window opens, allowing a just-finished remote teardown to become visible in GitHub Actions. If a correlated mutation remains active or GitHub cannot be queried by then, the inventory is skipped and the audit job fails closed.

## Deploy workflow behavior

O script de deploy usa o namespace `auto-shop-hml` em staging e `auto-shop-prd` em produção. No primeiro deploy de cada namespace, gera uma senha Redis aleatória e grava `REDIS_PASSWORD` e `REDIS_URL` em `auto-shop-redis-credentials`, sem incluí-los em logs ou artefatos. O Redis é efêmero, sem persistência, e aceita conexões somente dos Pods da API. O NGINX Ingress segue restrito ao ambiente local; em AWS, o API Gateway encaminha o tráfego ao ALB interno. O job de deploy usa `GITHUB_TOKEN` apenas para ler a imagem GHCR e OIDC para obter credenciais AWS temporárias; nenhum access key AWS fica no repositório.

## Pré-requisitos do cluster para migrations

O build publica tags imutáveis `sha-<7>` no GHCR. Após a validação da janela de lifecycle e a autenticação OIDC, o job de deploy usa `GITHUB_TOKEN` com `packages: read` para ler a imagem exata do commit atual, valida o rótulo OCI de revisão e a espelha para o repositório privado ECR `auto-shop-system`. O helper exige que o repositório exista na conta e região configuradas, valide URI e imutabilidade de tags e confirma que a imagem no ECR é idêntica à origem. `deploy.sh` recebe a referência ECR com tag `sha-<7>`.

Os nós EKS precisam de `ecr:GetAuthorizationToken`, `ecr:BatchGetImage`, `ecr:BatchCheckLayerAvailability` e `ecr:GetDownloadUrlForLayer` na role de instância (ou na role de execução do Fargate). A ação do token exige escopo Resource *. Os nós também precisam de acesso de rede à API ECR, ao registry Docker ECR e ao S3 que hospeda as camadas da imagem; use NAT ou os endpoints VPC correspondentes. Com permissão da role do nó, não é necessário configurar credenciais do registry no Kubernetes.

O Terraform desta aplicação limita as permissões de mirror da role de deploy ao ARN do repositório `auto-shop-system`; a permissions boundary é externa e precisa permitir as mesmas ações ECR. Antes de habilitar um gate de deploy, confirme externamente que a role dos nós e a boundary permitem essas ações, que o repositório ECR existe com tags imutáveis e que o package GHCR concede leitura ao `GITHUB_TOKEN` deste repositório. Esses settings externos não foram alterados nem verificados.

O Job de migrations usa EKS Pod Identity para ler o segredo do banco. A infraestrutura do cluster precisa instalar e manter pronto o add-on `eks-pod-identity-agent`; `deploy.sh` verifica o DaemonSet antes de alterar o namespace. Os nós de trabalho também precisam acessar a API EKS Auth, usada pelo agente, e o Secrets Manager, usado pelo Job. Se as sub-redes não tiverem NAT, configure VPC interface endpoints com DNS privado e regras de Security Group que permitam HTTPS na porta 443.
Pushes to `main` and `develop` continue to build and publish the backend image. They do not change a running environment. Deployments require `workflow_dispatch` with the coordinator-provided `session_id`, `started_at`, and `session_mode`; the CD workflows validate those fields against the BRT date and authorized window. HML frontend deployment follows the backend and also requires `DEPLOY_STAGING_FRONTEND_ENABLED=true`. PRD synthetic seed requires `ALLOW_SYNTHETIC_SEED_IN_PRD=true`.

The deploy workflows do not need daily Environment variables for session IDs or timestamps. `STAGING_ACTIVE`, `STAGING_SESSION_AUTHORIZED`, and `STAGING_SESSION_MODE=hml` are static HML authorization gates. PRD authorization uses `ENVIRONMENT_ACTIVE` and `ENVIRONMENT_WINDOW_AUTHORIZED`; opening additionally requires the lifecycle gates below. No extra 21:30 deploy cutoff is used. The validated teacher availability window ends at 22:00 BRT. Workflow-dispatch inputs accept `session_token` optionally so a manual dispatch can be started, but validation fails before AWS access if it is absent or invalid.

As variáveis de repositório `DEPLOY_STAGING_ENABLED` e `DEPLOY_PRODUCTION_ENABLED` controlam os jobs de deploy do backend. Mantenha ambas ausentes ou `false` até o ambiente alvo, a infraestrutura AWS e os smoke checks estarem prontos. Com o gate desligado, o build da imagem continua e os jobs de deploy são ignorados.

O deploy do frontend tem gates independentes: `DEPLOY_STAGING_FRONTEND_ENABLED` e `DEPLOY_PRODUCTION_FRONTEND_ENABLED`. Ambos precisam estar ausentes ou `false` enquanto a publicação do frontend não estiver autorizada. Habilitar o deploy do backend não publica o frontend. Quando o respectivo gate do frontend estiver `true`, o workflow reutilizável só roda depois do deploy do backend correspondente; ele compila o Angular, lê do SSM o bucket S3 e o ID da distribuição CloudFront, sincroniza o bundle e invalida a distribuição.
## Default gates and required configuration

All gates below must be explicitly configured before an opening. Missing values behave as false. No workflow writes GitHub Environment variables.

| Scope | Required values |
|---|---|
| PRD | `ENVIRONMENT_SCHEDULE_ENABLED=true`, `PRD_LIFECYCLE_AUTOMATION_READY=true`, `PRD_COST_EXCEPTION_APPROVED=true`, `ENVIRONMENT_ACTIVE=true`, `ENVIRONMENT_WINDOW_AUTHORIZED=true` |
| HML | `STAGING_ACTIVE=true`, `STAGING_SESSION_AUTHORIZED=true`, `STAGING_SESSION_MODE=hml` |
| PRD backend deploy | `DEPLOY_PRODUCTION_ENABLED=true`, `ALLOW_SYNTHETIC_SEED_IN_PRD=true` |
| PRD frontend deploy | `DEPLOY_PRODUCTION_ENABLED=true`, `DEPLOY_PRODUCTION_FRONTEND_ENABLED=true`, `ALLOW_SYNTHETIC_SEED_IN_PRD=true` |
| HML backend deploy | `DEPLOY_STAGING_ENABLED=true` |
| HML frontend deploy | `DEPLOY_STAGING_ENABLED=true`, `DEPLOY_STAGING_FRONTEND_ENABLED=true` |

The central workflows also require repository variables for AWS account/region, lifecycle alert topic, K8s and database repository/ref, edge settings, and the reviewed PRD/HML daily cost estimate. Refs must be `main` for infrastructure repositories. The app dispatch uses `main` for PRD and `develop` for HML. The explicit secret `LIFECYCLE_CROSS_REPO_TOKEN` must have Actions dispatch/read/cancel access on the app, K8s, and database repositories. There is no `GITHUB_TOKEN` fallback.

The shared secret `LIFECYCLE_SESSION_SIGNING_KEY` is unset by default. Before enabling lifecycle dispatches, configure the same value as a GitHub Actions secret in the coordinator, app, K8s, and database repositories (prefer an organization secret scoped to those repositories). Use a random UTF-8 string of at least 32 bytes; for example, generate 32 random bytes and encode them as 64 lowercase hex characters. The coordinator signs `session_mode|session_id|started_at` with HMAC-SHA256; the resulting 64-character capability is included in child `workflow_dispatch` inputs and is visible through workflow event metadata. Restrict Actions run access to trusted operators. This capability is reusable for the session; keep PRD readiness false until a short-lived, single-use authorization transport replaces it. A missing key, missing token, malformed session, or mismatched signature fails closed.

| Variável ou secret | Exemplo | Uso |
|---|---|---|
| Variável `AWS_REGION` | `us-east-1` | Região de EKS, SSM e S3 |
| Variáveis `AWS_DEPLOY_ROLE_ARN_HML` e `AWS_DEPLOY_ROLE_ARN_PRD` | Outputs `github_deploy_role_arn_staging` e `github_deploy_role_arn_production` da stack AWS | Acesso ao EKS e leitura dos parâmetros SSM do backend por stage |
| Variáveis `AWS_FRONTEND_DEPLOY_ROLE_ARN_HML` e `AWS_FRONTEND_DEPLOY_ROLE_ARN_PRD` | Outputs `github_frontend_deploy_role_arn_staging` e `github_frontend_deploy_role_arn_production` da stack AWS | Escrita somente no bucket e invalidação somente da distribuição CloudFront do stage |

As roles são separadas por finalidade: a role de backend descreve o cluster EKS e lê apenas os parâmetros SSM necessários para o deploy; ela não pode publicar o frontend. A role do frontend lê apenas os destinos SSM do stage e publica no bucket S3 correspondente, podendo invalidar apenas a distribuição CloudFront correspondente. A autorização de acesso à API do EKS (access entry ou `aws-auth`) vem do repositório de infraestrutura, não deste workflow.
AWS workflow secrets include `AWS_COST_READER_ROLE_ARN`, `AWS_EDGE_LIFECYCLE_ROLE_ARN`, and `LIFECYCLE_ALERT_ROLE_ARN`. The auth preflight role is declared in `infra/aws` and its fixed ARN is built from `AWS_ACCOUNT_ID`; its trust requires this repository's `operations` environment. The stage-scoped preflight reads that stage's auth ARN contract plus the shared VPC, private subnet, and Lambda security group contracts, then checks only that stage's Lambda configuration and database-secret name. Opening HML does not depend on the production auth Lambda. The preflight verifies account and region, Lambda active/update status, and exact VPC/subnet/security group matches; it never reads Secrets Manager values. The edge secret is passed only as a Secrets Manager ARN reference; the JWT value is not read by the coordinator. Configure the public frontend/API URLs for health probes and the edge domain/execute-api options explicitly.

`PRD_LIFECYCLE_AUTOMATION_READY` stays false until two complete opening and closing cycles, including the orphan audit and cost evidence, have succeeded. `PRD_COST_EXCEPTION_APPROVED` stays false until the ADR-0071 exception is documented and approved.

## SSM parameter contract

- `/frontend/hml/bucket-name` e `/frontend/hml/distribution-id`
- `/frontend/prd/bucket-name` e `/frontend/prd/distribution-id`
- `/eks/cluster-name`
- `/database/secrets/migrations-hml-arn` e `/database/secrets/migrations-prd-arn` (ARN não secreto do segredo de migrations por database)
- `/events/service-order-bus-name` e `/events/service-order-bus-name/prd`
- `/events/service-order-publisher-role-arn/hml` e `/events/service-order-publisher-role-arn/prd`

## Cost and recovery evidence
Each opening and close uploads a JSON evidence artifact with two separate records: the operator-maintained daily floor is a planning estimate, while AWS Cost Explorer `UnblendedCost` is observed billing over the prior 30 days. Cost Explorer data can lag usage and is not a real-time meter. If the role, API, or billing permission is unavailable, the report records observed billing as unavailable and the lifecycle fails closed; it does not infer a cost value.

If opening stops after a partial cross-repository success, do not launch another session that day. Inspect the correlated remote runs and rerun the same central opening run only when its failed phase is safe to retry. A failed close can be retried for that session, but it starts the close sequence again; inspect completed phases first because remote destroy operations may not be idempotent. If the cleanup window expires or the remote run cannot be correlated, use the infrastructure repository's reviewed recovery process and verify the orphan inventory before reopening. The orphan audit can overlap with a remote teardown that did not acknowledge cancellation; inspect both run results before considering the session closed. A close with no matching opening or no mutating step is a no-op. The URL may remain reachable while the backend is unavailable; health is never declared successful from a preflight alone.

## Scope limits

O Terraform em [`infra/aws/github_oidc.tf`](../infra/aws/github_oidc.tf) pode criar roles cuja trust policy fica restrita a este repositório, ao GitHub Environment e à branch esperada: `hml` somente para `develop` e `prd` somente para `main`. Mantenha também as regras de deployment branch nesses Environments. Configure os outputs Terraform por stage nas variáveis de repositório listadas acima somente depois de aplicar e revisar a stack AWS. Enquanto os outputs estiverem ausentes, os deploys falham fechados.
These edits declare the coordinator, dispatch contracts, and read-only auth preflight role in Terraform; they do not change GitHub Environment settings, create AWS roles in the account, configure billing permissions, or run AWS/Terraform applies. Full lifecycle availability still depends on the matching K8s/database workflow contracts being merged and on the gates and credentials above being configured. Local verification results are recorded with the implementation PRs. No live lifecycle cycle or AWS apply/destroy/deploy was run.

The current HMAC session capability is sent in `workflow_dispatch` inputs. GitHub exposes workflow-dispatch values through the event and inputs contexts, so treat the capability as visible to users who can inspect workflow runs. Keep workflow access limited to trusted operators and keep readiness gates false until the capability is replaced with a short-lived, single-use authorization mechanism.
