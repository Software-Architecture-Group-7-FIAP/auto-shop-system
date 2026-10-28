# Borda AWS e staging

Terraform da borda de API e frontend descrita na issue [#113](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/issues/113), com suporte ao staging da [#87](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/issues/87).

Este repositório contém a definição da infraestrutura. Isso não significa que os recursos foram aplicados nem que o staging passou pelos smoke checks.

## Recursos

- API Gateway REST regional com os stages `hml` e `prd`.
- VPC Link V2 do API Gateway para o ALB interno, com regras de security group limitadas às portas dos listeners.
- CORS preflight for web-session and administrative routes is handled by FastAPI; the customer-token OPTIONS route reaches the stage-specific Lambda.
- The customer-token and JWKS endpoints invoke the Lambda ARN for their own stage, read from SSM.
- Regional WAF with Common Rule Set and a high coarse source-IP cap; CloudFront WAF applies viewer-IP limits for authentication, public/customer APIs, and customer-token requests.
- Dois buckets S3 privados e distribuições CloudFront para o Angular, com OAC.
- Certificado ACM para `api.oficina-workshop.com.br`, `app-hml.oficina-workshop.com.br` e `app.oficina-workshop.com.br`.
- Logs de acesso da API e logs do WAF no CloudWatch.
- Roles opcionais de GitHub OIDC para deploy no Kubernetes e publicação do frontend.

## Mapeamento dos ambientes

| GitHub Environment | Stage da API | Namespace Kubernetes | Host do frontend |
|---|---|---|---|
| `staging` | `hml` | `auto-shop-hml` | `app-hml.oficina-workshop.com.br` |
| `production` | `prd` | `auto-shop-prd` | `app.oficina-workshop.com.br` |

A stack upstream precisa exportar os parâmetros abaixo sob `upstream_ssm_prefix` (padrão `/auto-shop/staging`):

- `network/vpc-id`
- `network/workload-private-subnet-ids`
- `eks/cluster-name`
- `gateway/internal-alb-arn`
- `gateway/listener-arn/hml` and `gateway/listener-arn/prd`
- `auth/customer-token/function-arn/hml` and `auth/customer-token/function-arn/prd`
- `database/secrets/migrations-hml-arn` and `database/secrets/migrations-prd-arn`
- `database/iam/migrations-hml-read-policy-arn` and `database/iam/migrations-prd-read-policy-arn`

Os fluxos de sessão do EKS e do banco são pré-requisitos separados para a issue #87 e precisam ser coordenados com os repositórios responsáveis.

O contrato upstream publica um ARN de Lambda por stage: `/auth/customer-token/function-arn/hml` e `/auth/customer-token/function-arn/prd`. A API Gateway usa o ARN correspondente a `hml` ou `prd`; o plan depende que os dois parametros existam. A Lambda e publicada pelo repositorio `lambda-auth` e sua alteracao correspondente ainda precisa passar pelo PR upstream.

Há outra diferença de contrato a resolver antes de declarar a integração de JWT concluída: a ADR define o issuer na raiz do domínio da API, enquanto o JWKS é publicado sob os base paths `/hml` e `/prd`. Confirme que o Lambda emite esse issuer e que os dois documentos JWKS correspondem às chaves usadas nos tokens.

## Entradas e revisão Terraform

Pré-requisitos: Terraform >= 1.10, credenciais AWS para a conta alvo e os parâmetros SSM upstream listados acima. O state usa o bucket S3 compartilhado e lock nativo, conforme a ADR-0071. `aws_region` é limitado a `us-east-1` porque o certificado será usado pelo CloudFront.

```bash
terraform -chdir=infra/aws init
terraform -chdir=infra/aws fmt -recursive
terraform -chdir=infra/aws validate
terraform -chdir=infra/aws plan -var-file=terraform.tfvars
```

Forneca `jwt_secret_arn` com o ARN de um segredo do Secrets Manager. O valor armazenado como SecretString deve ser igual ao `ACCESS_TOKEN_SECRET` usado pelo backend. O Terraform passa somente o ARN; a role exclusiva do authorizer le o valor em runtime. Nunca passe o segredo por tfvars, variaveis Terraform com valor, plano, log ou state. A chave do state eh `auto-shop-system/infra/aws/staging/terraform.tfstate`. Mantenha o arquivo do plano local e revise as mudancas antes de qualquer apply. O plano e as mudancas AWS seguem o processo de aprovacao da ADR-0071.

## Ativação dos domínios próprios

O padrão é `enable_custom_domains = false`, para permitir solicitar o certificado ACM antes da publicação dos registros DNS.

1. Revise o plano Terraform e crie o certificado.
2. Consulte o output `acm_dns_validation_records` e publique os CNAMEs no Registro.br.
3. Aguarde o ACM marcar o certificado como emitido.
4. Defina `enable_custom_domains = true`, revise o plano e aplique os mappings da API e os aliases do CloudFront.
5. Publique CNAMEs para `api.oficina-workshop.com.br`, `app-hml.oficina-workshop.com.br` e `app.oficina-workshop.com.br`. Use `custom_domain_target` para a API e `frontend_deploy_targets[*].distribution_domain` para CloudFront.
6. Faça smoke checks nos dois base paths da API (`/hml` e `/prd`) e nos dois domínios do frontend.
7. Somente depois desses checks, defina `disable_execute_api_endpoint = true` em um plano revisado separadamente.

Os registros DNS são gerenciados manualmente no Registro.br; esta stack Terraform não gerencia uma zona Route 53.

## Deploy do frontend

O bundle Angular é igual nos dois stages e chama a API por caminhos relativos `/api/v1/...`. O comportamento `api/*` de cada distribuição encaminha as chamadas ao API Gateway com o prefixo `hml` ou `prd`. Assim, a sessão permanece no domínio do frontend e os caminhos dos cookies continuam válidos.

O workflow reutilizável compila `frontend/` com Node 18, lê do SSM o bucket e o ID da distribuição do stage, sincroniza o bundle de produção no S3 e invalida o cache do CloudFront. O `index.html` recebe headers `no-cache`; os assets com hash recebem cache de longa duração. O workflow de CI executa separadamente lint, checagem de tipos, build e testes do frontend.

Os gates de deploy dos GitHub Environments devem permanecer desligados até a infraestrutura e os smoke checks necessários estarem prontos. Os buckets S3 mantêm `force_destroy = false`; esvazie os dois buckets antes de `terraform destroy` para que a remoção não apague objetos sem uma ação explícita.

## Evidências de staging pendentes para #87

O mapeamento de namespaces e stages está representado neste repositório, mas a issue #87 só estará concluída após demonstrar uma sessão completa de staging. O repositório `database-infra` ainda precisa publicar credenciais e políticas de leitura distintas para migrations em HML e PRD; não use o master `owner` para executar migrations. Também faltam a orquestração e o teardown upstream da sessão, smoke checks do fluxo de negócio, evidência de HPA na AWS e um teardown sem recursos órfãos. O smoke local com Kind não comprova staging na AWS.
