# CD: build, deploy e gates de staging

O pipeline cria a imagem do backend e pode publicar a API e o frontend Angular no stage associado a cada branch:

```text
PR -> ci.yml -> merge em develop -> backend em staging -> frontend em hml
merge develop em main -> backend em production -> frontend em prd
```

## Validações do pull request

[`ci.yml`](./workflows/ci.yml) roda em pull requests e pushes para `develop` e `main`. Valida a aplicação Python, os manifests Kubernetes e o Terraform; também roda lint, checagem de tipos, build e testes do frontend. Os checks obrigatórios de branch protection estão relacionados à issue [#91](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/issues/91).

## Imagem do backend

Após o merge, o workflow reutilizável publica uma imagem imutável `sha-<7 caracteres>` no GHCR:

| Branch | Workflow | Destino |
|---|---|---|
| `develop` | `cd-staging.yml` | GitHub Environment `staging`, API stage `hml` |
| `main` | `cd-prod.yml` | GitHub Environment `production`, API stage `prd` |

O script de deploy usa o namespace `auto-shop-hml` em staging e `auto-shop-prd` em produção. No primeiro deploy de cada namespace, gera uma senha Redis aleatória e grava `REDIS_PASSWORD` e `REDIS_URL` em `auto-shop-redis-credentials`, sem incluí-los em logs ou artefatos. O Redis é efêmero, sem persistência, e aceita conexões somente dos Pods da API. O NGINX Ingress segue restrito ao ambiente local; em AWS, o API Gateway encaminha o tráfego ao ALB interno. O GHCR usa `GITHUB_TOKEN`, sem access key AWS.

## Pré-requisitos do cluster para migrations

O `GITHUB_TOKEN` autentica o runner ao publicar no GHCR; ele não configura credenciais de pull nos nós EKS. Os manifests atuais não definem `imagePullSecrets`, então o backend precisa aceitar pull anônimo. Os workflows CD validam isso com `docker pull` sem login antes de configurar credenciais AWS. Se o check retornar 401, mantenha o gate de deploy desligado e escolha entre tornar o package público ou implementar uma credencial de pull persistente para o cluster. O endpoint GHCR respondeu 401 para pull anônimo em 2026-10-29.

O Job de migrations usa EKS Pod Identity para ler o segredo do banco. A infraestrutura do cluster precisa instalar e manter pronto o add-on `eks-pod-identity-agent`; `deploy.sh` verifica o DaemonSet antes de alterar o namespace. Os nós de trabalho também precisam acessar a API EKS Auth, usada pelo agente, e o Secrets Manager, usado pelo Job. Se as sub-redes não tiverem NAT, configure VPC interface endpoints com DNS privado e regras de Security Group que permitam HTTPS na porta 443.

## Gates de deploy do backend e frontend

As variáveis de repositório `DEPLOY_STAGING_ENABLED` e `DEPLOY_PRODUCTION_ENABLED` controlam os jobs de deploy do backend. Mantenha ambas ausentes ou `false` até o ambiente alvo, a infraestrutura AWS e os smoke checks estarem prontos. Com o gate desligado, o build da imagem continua e os jobs de deploy são ignorados.

O deploy do frontend tem gates independentes: `DEPLOY_STAGING_FRONTEND_ENABLED` e `DEPLOY_PRODUCTION_FRONTEND_ENABLED`. Ambos precisam estar ausentes ou `false` enquanto a publicação do frontend não estiver autorizada. Habilitar o deploy do backend não publica o frontend. Quando o respectivo gate do frontend estiver `true`, o workflow reutilizável só roda depois do deploy do backend correspondente; ele compila o Angular, lê do SSM o bucket S3 e o ID da distribuição CloudFront, sincroniza o bundle e invalida a distribuição.

## Configuração dos GitHub Environments

Crie os GitHub Environments `staging` e `production`. Restrinja os branches de deploy a `develop` e `main`, respectivamente. Exija ao menos um reviewer para `production`.

Configure cada Environment com:

| Variável ou secret | Exemplo | Uso |
|---|---|---|
| Variável `AWS_REGION` | `us-east-1` | Região de EKS, SSM e S3 |
| Secret `AWS_DEPLOY_ROLE_ARN` | ARN real da role de backend | Acesso a EKS e leitura dos parâmetros SSM do backend |
| Secret `AWS_FRONTEND_DEPLOY_ROLE_ARN` | ARN real da role do frontend | Escrita no bucket S3 do frontend e invalidação da distribuição CloudFront |

As roles são separadas por finalidade: a role de backend descreve o cluster EKS e lê apenas os parâmetros SSM necessários para o deploy; ela não pode publicar o frontend. A role do frontend lê apenas os destinos SSM do stage e publica no bucket S3 correspondente, podendo invalidar apenas a distribuição CloudFront correspondente. A autorização de acesso à API do EKS (access entry ou `aws-auth`) vem do repositório de infraestrutura, não deste workflow.

Por padrão, o workflow lê estes parâmetros SSM não secretos sob o prefixo `/auto-shop/staging`:

- `/frontend/hml/bucket-name` e `/frontend/hml/distribution-id`
- `/frontend/prd/bucket-name` e `/frontend/prd/distribution-id`
- `/eks/cluster-name`
- `/database/secrets/migrations-hml-arn` e `/database/secrets/migrations-prd-arn` (ARN não secreto do segredo de migrations por database)
- `/events/service-order-bus-name` e `/events/service-order-bus-name/prd`
- `/events/service-order-publisher-role-arn/hml` e `/events/service-order-publisher-role-arn/prd`

Esses parâmetros são criados por `infra/aws`. Se `upstream_ssm_prefix` mudar nessa stack, atualize também a entrada do workflow reutilizável nos workflows CD chamadores.

## Pré-requisitos de OIDC e infraestrutura

O Terraform em [`infra/aws/github_oidc.tf`](../infra/aws/github_oidc.tf) pode criar roles cuja trust policy fica restrita a este repositório, ao GitHub Environment e à branch esperada: `develop` para staging e `main` para production. Mantenha também as regras de deployment branch nos Environments. Configure `github_deploy_role_arn_staging` e `github_deploy_role_arn_production` como `AWS_DEPLOY_ROLE_ARN`, e `github_frontend_deploy_role_arn_staging` e `github_frontend_deploy_role_arn_production` como `AWS_FRONTEND_DEPLOY_ROLE_ARN` nos Environments correspondentes.

Antes de ativar os deploys, configure o acesso ao cluster EKS, a rede, os parâmetros SSM, o API Gateway, as funções Lambda de autenticação de cliente, o DNS e as distribuições de frontend. Siga [`infra/aws/README.md`](../infra/aws/README.md) e a [ADR-0071](../docs/architecture/decisions/ADR-0071-infraestrutura-cloud-fase-3.md). Não habilite produção antes de configurar a aprovação e os smoke checks.

A issue [#87](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/issues/87) segue aberta até que uma sessão completa de staging na AWS seja demonstrada, incluindo smoke tests de negócio, evidência de HPA, teardown coordenado e confirmação de que não restaram recursos. Um smoke local com Kind não comprova staging na AWS.
