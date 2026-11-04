# RFC-0006: Roteamento na borda (API Gateway REST)

- **Status:** aceita como direção arquitetural
- **Data:** 2026-11-02
- **Decisão relacionada:** [ADR-0073](../architecture/decisions/ADR-0073-api-gateway-borda-publica.md)
- **Issue:** [#88](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/issues/88)

## Resumo

Entrada pública única via **API Gateway REST** + **WAF**, com rotas para Lambda de autenticação e proxy HTTP para o backend no cluster (VPC Link V2 → ALB interno), conforme ADR-0073 e Terraform em `infra/aws/`.

## Rotas (conceitual)

| Tráfego | Destino |
| --- | --- |
| Login gateway / token cliente / JWKS | Integrações Lambda (`lambda-auth`) |
| Admin, público (aprovação), customer API, health | HTTP proxy → Ingress Kubernetes |
| Headers de correlação | `X-Correlation-ID` mapeado a partir do `requestId` do Gateway (ver doc #93 / PR #174) |

Autenticação admin continua no FastAPI (JWT HS256); cliente usa RS256/JWKS (ADR-0064 / ADR-0072).

## Consequências

- TLS e WAF na borda; certificados e domínios documentados em `infra/aws/README.md`.
- Evoluções (VPC Link V2 dedicado, rotas extras) seguem issues #113+ sem reescrever este RFC.

## Referências

- [infra/aws/README.md](../../infra/aws/README.md)
- [ADR-0073](../architecture/decisions/ADR-0073-api-gateway-borda-publica.md)
