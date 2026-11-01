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
| [ADR-0079](decisions/ADR-0079-registry-privado-ecr.md) | GHCR autenticado e mirror para ECR privado |

## Diagramas editáveis e exportados

| Diagrama | Fonte | SVG | PNG |
| --- | --- | --- | --- |
| Arquitetura AWS da Fase 3 | [componentes-fase-3.mmd](diagrams/componentes-fase-3.mmd) | [SVG](diagrams/componentes-fase-3.svg) | [PNG](diagrams/componentes-fase-3.png) |
| Autenticação de cliente | [autenticacao-cliente.mmd](diagrams/autenticacao-cliente.mmd) | [SVG](diagrams/autenticacao-cliente.svg) | [PNG](diagrams/autenticacao-cliente.png) |
| Abertura de OS | [abertura-os.mmd](diagrams/abertura-os.mmd) | [SVG](diagrams/abertura-os.svg) | [PNG](diagrams/abertura-os.png) |
| UML: identidade e cadastro | [Fonte](diagrams/database-uml-identidade-cadastro.mmd) | [SVG](diagrams/database-uml-identidade-cadastro.svg) | [PNG](diagrams/database-uml-identidade-cadastro.png) |
| UML: catálogo e orçamentos | [Fonte](diagrams/database-uml-catalogo-orcamentos.mmd) | [SVG](diagrams/database-uml-catalogo-orcamentos.svg) | [PNG](diagrams/database-uml-catalogo-orcamentos.png) |
| UML: ordens de serviço | [Fonte](diagrams/database-uml-ordens-servico.mmd) | [SVG](diagrams/database-uml-ordens-servico.svg) | [PNG](diagrams/database-uml-ordens-servico.png) |
| UML: estoque e compras | [Fonte](diagrams/database-uml-estoque-compras.mmd) | [SVG](diagrams/database-uml-estoque-compras.svg) | [PNG](diagrams/database-uml-estoque-compras.png) |
| Modelo relacional ER completo | [database-schema.mermaid](../database/database-schema.mermaid) | [SVG](diagrams/database-er.svg) | [PNG](diagrams/database-er.png) |

As quatro vistas UML cobrem as 20 tabelas do schema. Classes centrais são repetidas entre vistas para contextualizar as relações; elas continuam representando as mesmas tabelas. O ER permanece disponível como visão integral do esquema.

O diagrama AWS usa um subconjunto local de ícones do pacote [@aws-icons/iconify](https://www.npmjs.com/package/@aws-icons/iconify), versão 4.1.0, baseado nos [AWS Architecture Icons](https://aws.amazon.com/architecture/icons/). A AWS permite o uso desses ícones em diagramas de arquitetura por clientes e parceiros. O subconjunto está versionado em diagrams/aws-icons.json para que a renderização não dependa de CDN. Atribuição e origem estão em [aws-icons-credits.md](diagrams/aws-icons-credits.md).

## Regenerar as exportações

A fonte versionada é a autoridade para os diagramas. Com Node.js 22.13 ou superior, npm/npx e Python, rode a partir da raiz do repositório:

~~~powershell
poetry run python scripts/render_architecture_diagrams.py
~~~

O script fixa @mermaid-js/mermaid-cli em 12.0.0, lê os arquivos Mermaid e atualiza os SVGs e PNGs em docs/architecture/diagrams/. O ícone AWS utilizado pelo diagrama de componentes vem do subconjunto local em docs/architecture/diagrams/aws-icons.json. Regere as exportações no mesmo PR que altera uma fonte.
