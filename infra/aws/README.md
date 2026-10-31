# Borda AWS e staging

Terraform da borda de API e frontend descrita na issue [#113](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/issues/113), com suporte ao staging da [#87](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/issues/87).

Este repositório contém a definição da infraestrutura. Isso não significa que os recursos foram aplicados nem que o staging passou pelos smoke checks.

## Recursos

- API Gateway REST regional com os stages `hml` e `prd`.
- VPC Link V2 do API Gateway para o ALB interno, com regras de security group limitadas às portas dos listeners.
- CORS preflight for web-session and administrative routes is handled by FastAPI; the customer-token OPTIONS route reaches the stage-specific Lambda.
- The customer-token and JWKS endpoints invoke the Lambda ARN for their own stage, read from SSM.
- Regional WAF with Common Rule Set and one aggregate cap of 20,000 requests per five minutes per source IP; CloudFront WAF applies viewer-IP limits of 100 for customer-token requests, 300 for login, and 1,000 for public/customer APIs.
- Dois buckets S3 privados e distribuições CloudFront para o Angular, com OAC.
- Certificado ACM para `api.oficina-workshop.com.br`, `app-hml.oficina-workshop.com.br` e `app.oficina-workshop.com.br`.
- Logs de acesso da API e logs do WAF no CloudWatch.
- Roles opcionais de GitHub OIDC separadas para deploy do backend e publicação do frontend.
- EventBridge por stage, SNS para alertas por e-mail, DLQs SQS e roles IRSA para o publisher de falhas de OS (#117).
- Roles opcionais de GitHub OIDC para deploy no Kubernetes, publicação do frontend e preflight read-only do ciclo de vida.

## Mapeamento dos ambientes

| GitHub Environment | Stage da API | Namespace Kubernetes | Host do frontend |
|---|---|---|---|
| `staging` | `hml` | `auto-shop-hml` | `app-hml.oficina-workshop.com.br` |
| `production` | `prd` | `auto-shop-prd` | `app.oficina-workshop.com.br` |

A stack upstream precisa exportar os parâmetros abaixo sob o prefixo fixo `/auto-shop/staging`, compartilhado com o preflight read-only da Lambda:

Esta lista reúne apenas os parâmetros consumidos por esta stack. Para o banco, ela inclui os quatro parâmetros de migration; o contrato completo publicado por `database-infra` possui 16 chaves e está descrito na [PR #13](https://github.com/Software-Architecture-Group-7-FIAP/database-infra/pull/13).

- `network/vpc-id`
- `network/workload-private-subnet-ids`
- `network/lambda-security-group-id`
- `eks/cluster-name`
- `eks/oidc-provider-arn`
- `gateway/internal-alb-arn`
- `gateway/listener-arn/hml` and `gateway/listener-arn/prd`
- `auth/customer-token/function-arn/hml` and `auth/customer-token/function-arn/prd`
- `database/secrets/migrations-hml-arn`
- `database/secrets/migrations-prd-arn`
- `database/iam/migrations-hml-read-policy-arn`
- `database/iam/migrations-prd-read-policy-arn`

As roles de migration e as associacoes Pod Identity por ambiente pertencem a este repositorio. Elas leem somente os ARNs `migrations-hml` ou `migrations-prd` e a policy correspondente publicados por `database-infra`. A identidade `owner` fica exclusiva do Job de bootstrap, cuja role e ServiceAccount sao mantidas por `database-infra` em `auto-shop-ops`; `k8s-infra` fornece o cluster, o namespace e as politicas de rede. Os fluxos de sessao do EKS e do banco sao pre-requisitos separados para a issue #87 e precisam ser coordenados com os repositorios responsaveis.

Quando `enable_github_oidc = true`, esta stack também cria a role estável `auto-shop-staging-github-auth-preflight` e publica seu ARN no output `github_auth_preflight_role_arn`. O workflow de abertura constrói o ARN a partir da variável `AWS_ACCOUNT_ID`; não é necessário copiar um ARN para um secret. A trust policy exige o OIDC audience `sts.amazonaws.com` e o subject imutável deste repositório (`org ID 279547328` e `repository ID 1221936756`) no environment `operations`. As roles de deploy confiam somente nos environments `staging` e `production` usados pelos workflows. A policy read-only permite somente `ssm:GetParameters` nos cinco contratos SSM de auth/rede usados pelo preflight e `lambda:GetFunctionConfiguration` nas funções `lambda-auth-hml` e `lambda-auth-prd` (sufixos do nome-base configurável `auth_lambda_function_name`). A role não lê Secrets Manager, não altera recursos e não autoriza deploy.

O Terraform do repositório `lambda-auth` pode publicar um ARN por stage em `/auth/customer-token/function-arn/hml` e `/auth/customer-token/function-arn/prd`, usando `function_arn_ssm_parameter_name`. A publicação fica desativada por padrão; configure o caminho correspondente ao stage e use state separado para cada função. O API Gateway invoca a Lambda correspondente ao stage; o valor do ARN não é segredo.

O contrato de cliente usa `iss=https://api.oficina-workshop.com.br` e `aud=auto-shop-api` nos dois stages. O issuer permanece na raiz da API; HML usa `https://api.oficina-workshop.com.br/hml/.well-known/jwks.json` e PRD usa `https://api.oficina-workshop.com.br/prd/.well-known/jwks.json`. Os overlays Kubernetes já declaram esses valores. Configure `jwt_issuer` e `jwt_audience` do Terraform `lambda-auth` com os mesmos valores; o módulo publica somente o ARN da função no SSM. Antes de habilitar deploy, o smoke da sessão deve confirmar que cada JWKS contém o `kid` ativo do token daquele stage.

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

Os gates de deploy do backend (`DEPLOY_STAGING_ENABLED` e `DEPLOY_PRODUCTION_ENABLED`) devem permanecer desligados até a infraestrutura e os smoke checks necessários estarem prontos. A publicação do frontend usa os gates separados `DEPLOY_STAGING_FRONTEND_ENABLED` e `DEPLOY_PRODUCTION_FRONTEND_ENABLED`, ambos ausentes ou `false` enquanto a publicação não estiver autorizada. As roles OIDC também são separadas: a role de backend não pode gravar no S3 nem invalidar CloudFront. Os buckets S3 mantêm `force_destroy = false`; esvazie os dois buckets antes de `terraform destroy` para que a remoção não apague objetos sem uma ação explícita.

## Eventos de falha de OS (#117)

Esta stack cria um bus EventBridge isolado para cada stage. O contrato do SSM é:

- HML: `${upstream_ssm_prefix}/events/service-order-bus-name`.
- PRD: `${upstream_ssm_prefix}/events/service-order-bus-name/prd`.
- Role IRSA: `${upstream_ssm_prefix}/events/service-order-publisher-role-arn/{hml|prd}`.

As regras aceitam somente `source=auto-shop.service-orders`, `detail-type=ServiceOrderProcessingFailed` e `detail.event_version=1`. O EventBridge entrega ao tópico SNS; falhas na entrega são tentadas novamente por até 24 horas e podem seguir para a DLQ SQS standard do stage. A política da fila permite `sqs:SendMessage` somente ao EventBridge, para a regra correspondente e na conta atual. A política do tópico limita `sns:Publish` às duas regras do projeto e aos alarmes de DLQ. O tópico usa uma chave KMS gerenciada pelo projeto, com rotação e janela de exclusão de sete dias; a política limita o uso ao contexto da topic. As filas usam SSE gerenciada pelo SQS.

Um alarme CloudWatch por stage publica no mesmo tópico SNS quando a respectiva DLQ contém uma mensagem visível. O ServiceAccount `auto-shop-backend` em cada namespace recebe a role de publicação por IRSA. A trust policy valida o audience `sts.amazonaws.com` e o subject exato do namespace e ServiceAccount. O provedor OIDC do cluster precisa existir e ser publicado por `k8s-infra` em `eks/oidc-provider-arn`. A rede privada dos pods também precisa ter saída ao endpoint EventBridge, por NAT ou endpoint de VPC gerenciado pela stack de rede.

A chave KMS própria gera custo recorrente enquanto existir; o destroy agenda a exclusão após sete dias. A DLQ não tem consumidor de replay automático: a mensagem dispara o alarme e deve ser inspecionada antes de qualquer reenvio.

Para habilitar e-mail, forneça `service_order_alert_email` em um arquivo local não versionado ou via `TF_VAR_service_order_alert_email`. O Terraform não grava o endereço no repositório. Se o valor estiver vazio, os recursos EventBridge/SNS/DLQ continuam disponíveis, mas nenhuma inscrição de e-mail é criada. O destinatário recebe uma mensagem de confirmação da AWS e precisa aceitá-la antes dos testes de recebimento.

Os deploys HML/PRD leem do SSM somente os nomes/ARNs exatos do bus e da role IRSA e injetam esses valores nos manifests, sem conceder `ssm:GetParameter` ao backend. O payload do e-mail contém apenas stage, IDs técnicos e timestamp; falhas no próprio `PutEvents` continuam sendo best-effort na aplicação e não são cobertas pela DLQ do target.

## Evidências de staging pendentes para #87

O mapeamento de namespaces e stages está representado neste repositório, mas a issue #87 só estará concluída após demonstrar uma sessão completa de staging. O repositório `database-infra` ainda precisa publicar credenciais e políticas de leitura distintas para migrations em HML e PRD; não use o master `owner` para executar migrations. Também faltam a orquestração e o teardown upstream da sessão, smoke checks do fluxo de negócio, evidência de HPA na AWS e um teardown sem recursos órfãos. O smoke local com Kind não comprova staging na AWS.
