# RFCs — Auto Shop

Propostas técnicas para as decisões estruturais da Fase 3, formalizadas antes do ADR correspondente.

| RFC | Tema | Status | ADR relacionado |
| --- | --- | --- | --- |
| [RFC-0001](./RFC-0001-escolha-cloud-aws.md) | Escolha do provedor de nuvem (AWS) | Aceita como direção arquitetural | [ADR-0071](../architecture/decisions/ADR-0071-infraestrutura-cloud-fase-3.md) |
| [RFC-0002](./RFC-0002-banco-postgresql-rds.md) | Banco relacional PostgreSQL em Amazon RDS | Aceita como direção arquitetural | [ADR-0071](../architecture/decisions/ADR-0071-infraestrutura-cloud-fase-3.md) |
| [RFC-0003](./RFC-0003-autenticacao-cliente-cpf-jwt.md) | Autenticação de cliente por CPF e JWT (RS256/KMS + JWKS) | Aceita para a entrega acadêmica; implantação e homologação pendentes | [ADR-0064](../architecture/decisions/ADR-0064-autenticacao-cliente-cpf-jwt.md) |
| [RFC-0004](./RFC-0004-observabilidade-new-relic.md) | Observabilidade — New Relic | Aceita como direção; instrumentação HML pendente (#92) | [ADR-0078](../architecture/decisions/ADR-0078-observabilidade-new-relic.md) |
| [RFC-0005](./RFC-0005-deploy-multi-repositorio-cicd.md) | CI/CD e deploy nos quatro repositórios | Aceita como direção operacional | [ADR-0074](../architecture/decisions/ADR-0074-estrategia-branches-e-ci.md) |
| [RFC-0006](./RFC-0006-api-gateway-roteamento-borda.md) | Roteamento API Gateway + WAF | Aceita como direção arquitetural | [ADR-0073](../architecture/decisions/ADR-0073-api-gateway-borda-publica.md) |

Justificativa detalhada do banco, com modelo ER e explicação dos relacionamentos: [justificativa-banco-postgresql.md](../architecture/justificativa-banco-postgresql.md).

Quando uma RFC é aceita, a decisão operacional correspondente é registrada como ADR numerado em `docs/architecture/decisions/`; o conteúdo da RFC não é reescrito retroativamente.
