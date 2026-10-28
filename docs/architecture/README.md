# Arquitetura — Auto Shop

Documentação de arquitetura da Fase 2 (Kubernetes local) e Fase 3 (operacional: Gateway, CI/CD, observabilidade).

## Diagramas

| Fase | Fonte Mermaid | Export |
| --- | --- | --- |
| Fase 2 — app no cluster local | [fase2-architecture.mmd](./fase2-architecture.mmd) | [PNG](./fase2-architecture.png), [SVG](./fase2-architecture.svg) |
| Fase 3 — operacional ponta a ponta | [fase-operacional.mmd](./fase-operacional.mmd) | Exportar PNG/SVG localmente com `@mermaid-js/mermaid-cli` (fatia 2 da #95) |

Modelo de dados: [`docs/database/database-schema.mermaid`](../database/database-schema.mermaid).

## ADRs (`decisions/`)

| ADR | Tema |
| --- | --- |
| [ADR-0064](./decisions/ADR-0064-autenticacao-cliente-cpf-jwt.md) | JWT cliente CPF / JWKS |
| [ADR-0066/0067](./decisions/ADR-0066-0067-os-cliente-e-evento-de-falha.md) | OS do cliente + evento de falha |
| [ADR-0071](./decisions/ADR-0071-infraestrutura-cloud-fase-3.md) | Repositórios e topologia cloud |
| [ADR-0072](./decisions/ADR-0072-matriz-jwt-audiencias.md) | Matriz JWT web / gateway / customer |
| [ADR-0073](./decisions/ADR-0073-api-gateway-borda-publica.md) | API Gateway + WAF (#88) |
| [ADR-0074](./decisions/ADR-0074-estrategia-branches-e-ci.md) | Branches, CI, proteção (#89/#91) |

ADRs aceitos são imutáveis; novas decisões geram novo número.

## RFCs

Rascunhos e propostas operacionais: [`docs/rfc/`](../rfc/README.md) (fatia 2 da #95).

## Repositórios relacionados

- **Este repo:** `auto-shop-system` (backend + frontend + k8s app + templates CI)
- **lambda-auth**, **database-infra**, **k8s-infra** — ver ADR-0071
