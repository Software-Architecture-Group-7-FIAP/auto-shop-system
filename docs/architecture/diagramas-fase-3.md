# Arquitetura da Fase 3: decisões e diagramas

Esta página reúne os RFCs, ADRs e diagramas complementares da Fase 3. O desenho representa a arquitetura-alvo. A implementação ou aceitação de um PR não é evidência de que a infraestrutura esteja implantada ou validada em homologação.

## RFCs

| RFC | Decisão documentada |
| --- | --- |
| [RFC-0001](../rfc/RFC-0001-escolha-cloud-aws.md) | Escolha de AWS como provedor cloud |
| [RFC-0002](../rfc/RFC-0002-banco-postgresql-rds.md) | PostgreSQL e Amazon RDS |
| [RFC-0003](../rfc/RFC-0003-autenticacao-cliente-cpf-jwt.md) | CPF, JWT RS256, AWS KMS e JWKS |

## ADRs

| ADR | Decisão |
| --- | --- |
| [ADR-0075](decisions/ADR-0075-hpa-sem-cluster-autoscaler.md) | HPA para Pods; sem Cluster Autoscaler |
| [ADR-0076](decisions/ADR-0076-comunicacao-sincrona-e-evento-falha.md) | REST síncrono e evento de falha operacional |
| [ADR-0077](decisions/ADR-0077-hml-prd-por-namespace.md) | HML e PRD em namespaces e databases separados |
| [ADR-0078](decisions/ADR-0078-observabilidade-new-relic.md) | New Relic como plataforma de observabilidade |

## Diagramas editáveis e exportados

| Diagrama | Fonte Mermaid | SVG | PNG |
| --- | --- | --- | --- |
| Componentes da Fase 3 | [componentes-fase-3.mmd](diagrams/componentes-fase-3.mmd) | [SVG](diagrams/componentes-fase-3.svg) | [PNG](diagrams/componentes-fase-3.png) |
| Autenticação de cliente | [autenticacao-cliente.mmd](diagrams/autenticacao-cliente.mmd) | [SVG](diagrams/autenticacao-cliente.svg) | [PNG](diagrams/autenticacao-cliente.png) |
| Abertura de OS | [abertura-os.mmd](diagrams/abertura-os.mmd) | [SVG](diagrams/abertura-os.svg) | [PNG](diagrams/abertura-os.png) |
| Modelo ER | [database-schema.mermaid](../database/database-schema.mermaid) | [SVG](diagrams/database-er.svg) | [PNG](diagrams/database-er.png) |

## Regenerar as exportações

A fonte versionada é a autoridade para os diagramas. Com Node.js 22.13 ou superior, npm/npx e Python, rode a partir da raiz do repositório:

~~~powershell
poetry run python scripts/render_architecture_diagrams.py
~~~

O script fixa @mermaid-js/mermaid-cli em 12.0.0, lê os arquivos Mermaid e atualiza os SVGs e PNGs em docs/architecture/diagrams/. Regere as exportações no mesmo PR que altera uma fonte.
