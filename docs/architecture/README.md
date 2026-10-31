# Arquitetura — Auto Shop

Documentação de arquitetura da Fase 2 (Kubernetes local) e Fase 3 (operacional: Gateway, CI/CD, observabilidade).

## Diagramas

| Fase | Fonte Mermaid | Export |
| --- | --- | --- |
| Fase 2 — app no cluster local | [fase2-architecture.mmd](./fase2-architecture.mmd) | [PNG](./fase2-architecture.png), [SVG](./fase2-architecture.svg) |
| Fase 3 — operacional ponta a ponta | [fase-operacional.mmd](./fase-operacional.mmd) | Exportar PNG/SVG localmente com `@mermaid-js/mermaid-cli` (fatia 2 da #95) |
| Fase 3 — componentes (nuvem, APIs, banco, monitoramento) | [diagrams/componentes-fase-3.mmd](./diagrams/componentes-fase-3.mmd) | [PNG](./diagrams/componentes-fase-3.png), [SVG](./diagrams/componentes-fase-3.svg) |
| Sequência — autenticação do cliente (CPF → JWT → API) | [diagrams/autenticacao-cliente.mmd](./diagrams/autenticacao-cliente.mmd) | [PNG](./diagrams/autenticacao-cliente.png), [SVG](./diagrams/autenticacao-cliente.svg) |
| Sequência — abertura de OS | [diagrams/abertura-os.mmd](./diagrams/abertura-os.mmd) | [PNG](./diagrams/abertura-os.png), [SVG](./diagrams/abertura-os.svg) |

Modelo de dados: [`docs/database/database-schema.mermaid`](../database/database-schema.mermaid), exportado em [database-er.png](./diagrams/database-er.png) / [database-er.svg](./diagrams/database-er.svg). UML por domínio: [identidade e cadastro](./diagrams/database-uml-identidade-cadastro.mmd), [catálogo e orçamentos](./diagrams/database-uml-catalogo-orcamentos.mmd), [ordens de serviço](./diagrams/database-uml-ordens-servico.mmd), [estoque e compras](./diagrams/database-uml-estoque-compras.mmd) (PNG/SVG homônimos na mesma pasta).

## ADRs (`decisions/`)

| ADR | Tema |
| --- | --- |
| [ADR-0064](./decisions/ADR-0064-autenticacao-cliente-cpf-jwt.md) | JWT cliente CPF / JWKS |
| [ADR-0066/0067](./decisions/ADR-0066-0067-os-cliente-e-evento-de-falha.md) | OS do cliente + evento de falha |
| [ADR-0071](./decisions/ADR-0071-infraestrutura-cloud-fase-3.md) | Repositórios e topologia cloud |
| [ADR-0072](./decisions/ADR-0072-matriz-jwt-audiencias.md) | Matriz JWT web / gateway / customer |
| [ADR-0073](./decisions/ADR-0073-api-gateway-borda-publica.md) | API Gateway + WAF (#88) |
| [ADR-0074](./decisions/ADR-0074-estrategia-branches-e-ci.md) | Branches, CI, proteção (#89/#91) |
| [ADR-0075](./decisions/ADR-0075-hpa-sem-cluster-autoscaler.md) | HPA sem Cluster Autoscaler |
| [ADR-0076](./decisions/ADR-0076-comunicacao-sincrona-e-evento-falha.md) | Comunicação síncrona + evento de falha de OS |
| [ADR-0077](./decisions/ADR-0077-hml-prd-por-namespace.md) | HML e PRD por namespace (infraestrutura única) |
| [ADR-0078](./decisions/ADR-0078-observabilidade-new-relic.md) | Observabilidade — New Relic |

ADRs aceitos são imutáveis; novas decisões geram novo número.

## RFCs

Propostas técnicas aceitas e implementadas: [`docs/rfc/`](../rfc/README.md).

## Repositórios relacionados

- **Este repo:** `auto-shop-system` (backend + frontend + k8s app + templates CI)
- **lambda-auth**, **database-infra**, **k8s-infra** — ver ADR-0071
