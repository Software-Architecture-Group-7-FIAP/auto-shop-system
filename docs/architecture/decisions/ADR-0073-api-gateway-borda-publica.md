# ADR-0073: API Gateway REST como borda pública (#88)

- **Status:** Aceito (IaC em `infra/aws/`); deploy AWS pendente
- **Data:** 2026-10-23
- **Issue:** [#88 — API Gateway](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/issues/88)

## Contexto

O backend FastAPI roda no Kubernetes; a internet deve entrar por uma borda com throttling, WAF e autenticação diferenciada por rota. A implementação Terraform vive em `infra/aws/` neste repositório; Lambdas de autenticação evoluem em `lambda-auth`.

## Decisão

Usar **API Gateway REST regional** com:

- **WAFv2** associado ao stage (rate limit por IP + regras gerenciadas + SQLi).
- **Throttling** de stage e usage plan (`429` no Gateway).
- **Integrações:**
  - `AWS_PROXY` para Lambdas (`POST /auth/login`, e rotas de cliente quando configuradas).
  - `HTTP_PROXY` para backend (`/api/v1/admin/{proxy+}`, `/api/v1/public/{proxy+}`, `/api/v1/customer/{proxy+}`, `/health/{proxy+}`).
- **Authorizer JWT (Lambda TOKEN, HS256)** somente em `/api/v1/admin/*`, compartilhando segredo com o backend.
- **Access logs** JSON em CloudWatch (`requestId`, latência, status).
- **Correlação:** propagar `X-Correlation-ID` a partir de `$context.requestId` nas integrações HTTP (ver `infra/aws/api_gateway.tf` e [ADR futuro de logs #93]).

Rotas públicas sensíveis (`POST /auth/customer/token`, `GET /.well-known/jwks.json`) dependem de Lambda externa + permissões `lambda:InvokeFunction` restritas por path no API Gateway.

## Alternativas consideradas

| Opção | Motivo de rejeição |
| --- | --- |
| Expor Ingress diretamente | Sem WAF/throttling centralizado exigido pelo desafio |
| Authorizer único para admin + cliente | Cliente usa RS256/JWKS; admin usa HS256 — validadores distintos |
| HTTP API (v2) apenas | REST escolhido para compatibilidade com authorizer Lambda e mapeamento já implementado |

## Consequências

- Backend deve confiar em headers apenas após TLS terminado na borda; não reutilizar authorizer admin para JWT de cliente.
- Domínio customizado + ACM opcionais via variáveis Terraform (`domain_name`, `route53_zone_id`).
- Detalhes operacionais: [`infra/aws/README.md`](../../../infra/aws/README.md).

## Referências

- Diagrama: [`docs/architecture/fase-operacional.mmd`](../fase-operacional.mmd)
- Gateway local (dev): [`gateway/README.md`](../../../gateway/README.md)
