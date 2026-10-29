# Justificativa do PostgreSQL e modelo relacional

## Decisão

PostgreSQL é o banco relacional da aplicação. Na Fase 3, Amazon RDS for PostgreSQL é o destino cloud definido pelo ADR-0071. O banco continua sob responsabilidade de auto-shop-system, que mantém o schema e as migrations Alembic.

A justificativa é compatível com o modelo atual: entidades relacionadas por chaves estrangeiras, constraints de unicidade e transações que atualizam mais de um agregado durante a jornada de uma OS. A instância de staging não representa a capacidade ou disponibilidade de produção real.

## Diagramas UML e esquema ER

O modelo UML está dividido em quatro vistas editáveis para manter atributos, chaves e cardinalidades legíveis: [identidade e cadastro](diagrams/database-uml-identidade-cadastro.svg), [catálogo e orçamentos](diagrams/database-uml-catalogo-orcamentos.svg), [ordens de serviço](diagrams/database-uml-ordens-servico.svg) e [estoque e compras](diagrams/database-uml-estoque-compras.svg). As classes centrais aparecem repetidas nas vistas onde dão contexto às relações.

O [esquema ER completo](../database/database-schema.mermaid) e suas exportações são a visão integral do schema. Todas as fontes Mermaid e imagens são atualizadas por [render_architecture_diagrams.py](../../scripts/render_architecture_diagrams.py).

## Relações e regras representadas

- **Clientes e veículos:** um cliente pode possuir vários veículos; cada veículo referencia um cliente.
- **Cliente, veículo, orçamento e OS:** orçamentos e ordens de serviço referenciam cliente e veículo. A relação permite recuperar a jornada sem duplicar dados cadastrais.
- **Orçamento e linhas:** um orçamento contém linhas de serviço e produto com quantidade e preço unitário usados na proposta.
- **Orçamento e OS:** um orçamento pode gerar no máximo uma OS. budget_id na OS é opcional e preserva a origem sem exigir que toda OS tenha sido criada por orçamento.
- **OS e execução:** linhas de serviço/produto, reservas, retiradas de estoque, histórico de status e solicitações de compra referenciam a OS. Solicitações podem existir sem OS associada, conforme o schema.
- **OS e fatura:** a fatura referencia uma OS e o identificador da OS é único em invoices, limitando a uma fatura por ordem.
- **Produtos e fornecedores:** cada produto referencia seu fornecedor; solicitações de compra podem registrar quem atende ao pedido.
- **Serviço e produto:** service_product_lines registra a relação muitos-para-muitos entre serviços de catálogo e produtos necessários.
- **Compra e recebimento:** uma solicitação de compra pode possuir registros de recebimento; cada recebimento referencia a solicitação.
- **Usuários e auditoria:** sessões de refresh referenciam um usuário. O histórico de status pode registrar um usuário, mas também admite transições sem ator autenticado.

As cardinalidades seguem nulabilidade e unicidade das FKs no schema e nas migrations. Alterar relações exige atualizar schema e migrations.

## Por que PostgreSQL

- O domínio usa relações que precisam de integridade referencial entre cliente, veículo, orçamento, OS, estoque e faturamento.
- Transações mantêm consistentes mudanças que compõem ações como aprovar orçamento, criar OS e registrar reservas.
- PostgreSQL já é usado pela aplicação, migrations e testes de integração; mantê-lo reduz divergência entre desenvolvimento e homologação.
- SQLAlchemy e Alembic mantêm o acesso e a evolução do schema explícitos e versionados.
- Amazon RDS fornece o destino gerenciado requerido sem transferir a propriedade do schema ao repositório de infraestrutura.

## Limites do desenho

HML e PRD são bancos lógicos separados na infraestrutura efêmera do ADR-0071. O rótulo prd não equivale a conta, cluster, instância de banco ou arquitetura de alta disponibilidade independente. Backup, sizing, custo e operação seguem as decisões de infraestrutura.

## Referências

- [RFC-0002: PostgreSQL em Amazon RDS](../rfc/RFC-0002-banco-postgresql-rds.md)
- [ADR-0071: infraestrutura cloud](decisions/ADR-0071-infraestrutura-cloud-fase-3.md)
- [Amazon RDS for PostgreSQL](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_PostgreSQL.html)
