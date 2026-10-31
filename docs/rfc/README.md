# RFCs — Auto Shop

Propostas técnicas para as decisões estruturais da Fase 3, formalizadas antes do ADR correspondente.

| RFC | Tema | Status | ADR relacionado |
| --- | --- | --- | --- |
| [RFC-0001](./RFC-0001-escolha-cloud-aws.md) | Escolha do provedor de nuvem (AWS) | Aceita como direção arquitetural | [ADR-0071](../architecture/decisions/ADR-0071-infraestrutura-cloud-fase-3.md) |
| [RFC-0002](./RFC-0002-banco-postgresql-rds.md) | Banco relacional PostgreSQL em Amazon RDS | Aceita como direção arquitetural | [ADR-0071](../architecture/decisions/ADR-0071-infraestrutura-cloud-fase-3.md) |
| [RFC-0003](./RFC-0003-autenticacao-cliente-cpf-jwt.md) | Autenticação de cliente por CPF e JWT (RS256/KMS + JWKS) | Aceita para a entrega acadêmica; implantação e homologação pendentes | [ADR-0064](../architecture/decisions/ADR-0064-autenticacao-cliente-cpf-jwt.md) |

Justificativa detalhada do banco, com modelo ER e explicação dos relacionamentos: [justificativa-banco-postgresql.md](../architecture/justificativa-banco-postgresql.md).

Quando uma RFC é aceita, a decisão operacional correspondente é registrada como ADR numerado em `docs/architecture/decisions/`; o conteúdo da RFC não é reescrito retroativamente.
