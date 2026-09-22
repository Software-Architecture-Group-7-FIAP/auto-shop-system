# AWS API Gateway — Auto Shop

Terraform para a camada operacional descrita na issue **#88**:

- API Gateway REST regional
- Lambda de autenticação (`POST /auth/login`)
- Integração HTTP com backend Kubernetes
- Authorizer JWT (Lambda TOKEN + HS256)
- Throttling por stage e usage plan
- WAF regional (rate limit + managed rules + SQLi)
- Domínio customizado com ACM + Route53 (opcional)
- Access logs JSON no CloudWatch

## Pré-requisitos

- Terraform >= 1.6
- AWS CLI autenticado
- Backend FastAPI acessível via HTTPS a partir da internet (Ingress/NLB)
- Mesmo segredo JWT do backend (`SECRET_KEY` / `ACCESS_TOKEN_SECRET`)

## Rotas expostas

| Rota Gateway | Destino | Auth |
|--------------|---------|------|
| `POST /auth/login` | Lambda → backend `/api/v1/auth/gateway-login` | Pública |
| `/api/v1/admin/*` | HTTP proxy → backend | JWT authorizer |
| `/api/v1/public/*` | HTTP proxy → backend | Pública |
| `/health/*` | HTTP proxy → backend | Pública |

## Comandos

```bash
terraform -chdir=infra/aws init
terraform -chdir=infra/aws fmt -recursive
terraform -chdir=infra/aws validate

export TF_VAR_jwt_secret='your-shared-secret-at-least-32-chars'
terraform -chdir=infra/aws plan -var-file=terraform.tfvars
terraform -chdir=infra/aws apply -var-file=terraform.tfvars
```

## Domínio e HTTPS

Informe `domain_name` e `route53_zone_id` para:

1. Emitir certificado ACM com validação DNS
2. Criar `aws_api_gateway_domain_name` com TLS 1.2
3. Publicar alias A no Route53 apontando para o endpoint regional

Sem `route53_zone_id`, o certificado precisa ser validado manualmente antes do apply completo.

## Observabilidade

Access logs são enviados para `/aws/apigateway/auto-shop-<environment>` com:

- `requestId`, `ip`, `httpMethod`, `path`, `status`, `latencyMs`

Propague `X-Correlation-ID` usando `$context.requestId` nas integrações HTTP.

## Segurança

- WAF bloqueia SQLi e aplica rate limit por IP
- Throttling retorna `429` no API Gateway
- Authorizer rejeita JWT inválido/expirado com `401` antes do backend
- Segredos **não** devem ser versionados — use `TF_VAR_jwt_secret` ou arquivo local ignorado

## Relação com `infra/` (Kubernetes)

- `infra/` continua gerenciando recursos **dentro** do cluster
- `infra/aws/` gerencia a **borda pública** na AWS
- O backend aceita `Authorization: Bearer` nas rotas admin apenas para JWT com `aud: "gateway"` (emitido por `/api/v1/auth/gateway-login`); sessões web (`aud: "web"`) continuam exigindo cookie + CSRF
