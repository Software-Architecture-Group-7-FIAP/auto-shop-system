# RFC-0002: Banco relacional PostgreSQL em Amazon RDS

- **Status:** aceita como direção arquitetural
- **Data:** 2026-10-27
- **Decisão relacionada:** [ADR-0071](../architecture/decisions/ADR-0071-infraestrutura-cloud-fase-3.md)
- **Justificativa e modelo:** [PostgreSQL e modelo ER](../architecture/justificativa-banco-postgresql.md)

## Resumo

Manter PostgreSQL como banco relacional da aplicação e usar Amazon RDS for PostgreSQL como destino gerenciado da Fase 3. O schema e as migrations continuam sob responsabilidade de auto-shop-system.

## Contexto

O domínio mantém entidades relacionadas por chaves estrangeiras: clientes, veículos, orçamentos, ordens de serviço, produtos, reservas, solicitações de compra e faturas. Aprovar orçamento, reservar estoque e atualizar uma ordem exigem consistência entre vários registros.

A aplicação já usa SQLAlchemy, Alembic e PostgreSQL. O schema em [database-schema.mermaid](../database/database-schema.mermaid) descreve as relações utilizadas pelo domínio.

## Alternativas

| Alternativa | Avaliação para o Auto Shop |
| --- | --- |
| PostgreSQL em RDS | Preserva o engine e as migrations existentes; fornece um banco gerenciado compatível com a aplicação. |
| MySQL em RDS | Também é relacional, mas exigiria adaptar e revalidar schema, drivers, queries e migrations existentes. |
| DynamoDB como banco principal | Não corresponde ao modelo relacional nem às consultas que atravessam clientes, veículos, orçamentos e ordens de serviço. |
| PostgreSQL autogerenciado no cluster | Mantém o engine, mas acrescenta operação de armazenamento, backup e atualização ao cluster da aplicação. |

Aurora PostgreSQL não foi escolhido para esta entrega. A necessidade é manter PostgreSQL e demonstrar persistência gerenciada em infraestrutura efêmera; o projeto não documenta requisito de escala que justifique a troca para Aurora.

## Decisão

Usar Amazon RDS for PostgreSQL, versão e configuração definidas no ADR-0071. HML e PRD são databases lógicos distintos na mesma infraestrutura efêmera. A rede, criptografia, TLS e identidades de banco seguem o ADR-0071 e o repositório database-infra.

## Consequências

- PostgreSQL, schema e migrations têm um único proprietário: auto-shop-system.
- As migrations são versionadas e executadas antes do rollout da aplicação.
- As identidades owner, app_runtime e lambda_auth têm permissões diferentes; nenhum segredo é documentado neste RFC.
- O sizing de staging não estabelece disponibilidade ou capacidade de produção.
- A justificativa detalhada e as cardinalidades do modelo estão em [justificativa-banco-postgresql.md](../architecture/justificativa-banco-postgresql.md).

## Referências

- [Amazon RDS for PostgreSQL](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_PostgreSQL.html)
- [Esquema ER versionado](../database/database-schema.mermaid)
- [PostgreSQL documentation](https://www.postgresql.org/docs/)
