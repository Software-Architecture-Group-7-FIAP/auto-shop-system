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

## Gates de deploy do backend e frontend

As variáveis de repositório `DEPLOY_STAGING_ENABLED` e `DEPLOY_PRODUCTION_ENABLED` controlam os jobs de deploy. Mantenha ambas ausentes ou `false` até o ambiente alvo, a infraestrutura AWS e os smoke checks estarem prontos. Com o gate desligado, o build da imagem continua e os jobs de deploy são ignorados.

Quando o gate está ligado, o workflow publica o backend primeiro. O workflow reutilizável do frontend só roda depois que o deploy do backend termina com sucesso. Ele compila o Angular, lê do SSM o bucket S3 e o ID da distribuição CloudFront do stage, sincroniza o bundle e invalida a distribuição.

## Configuração dos GitHub Environments

Crie os GitHub Environments `staging` e `production`. Restrinja os branches de deploy a `develop` e `main`, respectivamente. Exija ao menos um reviewer para `production`.

Configure cada Environment com:

| Variável ou secret | Exemplo | Uso |
|---|---|---|
| Variável `AWS_REGION` | `us-east-1` | Região de EKS, SSM e S3 |
| Secret `AWS_DEPLOY_ROLE_ARN` | ARN real da role | Assumida via GitHub OIDC |

A role do Environment precisa de permissões restritas para descrever o cluster EKS, ler do SSM o ARN do segredo de migrations daquele stage e os destinos do frontend, listar o bucket S3, publicar e remover objetos do frontend e invalidar o CloudFront. A autorização de acesso à API do EKS (access entry ou `aws-auth`) vem do repositório de infraestrutura, não deste workflow.

Por padrão, o workflow lê estes parâmetros SSM não secretos sob o prefixo `/auto-shop/staging`:

- `/frontend/hml/bucket-name` e `/frontend/hml/distribution-id`
- `/frontend/prd/bucket-name` e `/frontend/prd/distribution-id`
- `/eks/cluster-name`
- `/database/secrets/migrations-hml-arn` e `/database/secrets/migrations-prd-arn` (ARN não secreto do segredo de migrations por database)

Esses parâmetros são criados por `infra/aws`. Se `upstream_ssm_prefix` mudar nessa stack, atualize também a entrada do workflow reutilizável nos workflows CD chamadores.

## Pré-requisitos de OIDC e infraestrutura

O Terraform em [`infra/aws/github_oidc.tf`](../infra/aws/github_oidc.tf) pode criar roles cuja trust policy fica restrita a este repositório, ao GitHub Environment e à branch esperada: `develop` para staging e `main` para production. Mantenha também as regras de deployment branch nos Environments. Os outputs são `github_deploy_role_arn_staging` e `github_deploy_role_arn_production`; configure cada valor como o secret `AWS_DEPLOY_ROLE_ARN` do Environment correspondente.

Antes de ativar os deploys, configure o acesso ao cluster EKS, a rede, os parâmetros SSM, o API Gateway, as funções Lambda de autenticação de cliente, o DNS e as distribuições de frontend. Siga [`infra/aws/README.md`](../infra/aws/README.md) e a [ADR-0071](../docs/architecture/decisions/ADR-0071-infraestrutura-cloud-fase-3.md). Não habilite produção antes de configurar a aprovação e os smoke checks.

A issue [#87](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/issues/87) segue aberta até que uma sessão completa de staging na AWS seja demonstrada, incluindo smoke tests de negócio, evidência de HPA, teardown coordenado e confirmação de que não restaram recursos. Um smoke local com Kind não comprova staging na AWS.
