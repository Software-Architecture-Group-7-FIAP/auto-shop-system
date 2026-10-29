# ADR-0078: New Relic para observabilidade da Fase 3

- **Status:** aceito como escolha de ferramenta; instrumentação e painéis pendentes
- **Data:** 2026-10-27
- **Issues relacionadas:** [#92: integração de observabilidade](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/issues/92), [#93: logs e correlação](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/issues/93), [#94: dashboards e alertas](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/issues/94)

## Contexto

A Fase 3 precisa correlacionar saúde da API, infraestrutura Kubernetes, Gateway, autenticação serverless e falhas de processamento de OS. A equipe precisa de uma plataforma comum para APM, métricas, logs e traces. A seleção do fornecedor é uma decisão de projeto; não significa que conta, agentes, permissões, painéis ou alertas estejam configurados.

## Alternativas consideradas

| Critério | New Relic | Datadog |
| --- | --- | --- |
| APM e infraestrutura | APM e monitoramento de infraestrutura disponíveis; instrumentação ainda precisa ser validada no projeto | APM e monitoramento de infraestrutura disponíveis; instrumentação ainda precisa ser validada no projeto |
| Kubernetes e AWS | Integrações para Kubernetes e serviços AWS; configuração e ingestão ainda pendentes | Integrações para Kubernetes e serviços AWS; configuração e ingestão ainda pendentes |
| Modelo de cobrança publicado | Faixa gratuita inclui 100 GB de ingestão por mês e um usuário Full Platform. A página informa US$ 0,40/GB para dados Original além da faixa gratuita; outros tipos de usuário e recursos podem ter cobrança | Cobrança por produtos e unidades diferentes, incluindo host de infraestrutura, container e métricas customizadas; o custo depende da seleção e do consumo |
| Adequação ao projeto | A faixa gratuita permite começar a validação acadêmica com um usuário técnico completo e usuários Basic para dashboards, consultas e alertas. Isso não garante custo zero se o volume ou as funções usadas ultrapassarem os limites | O modelo por host e componentes adicionais exigiria estimar hosts, containers, métricas e compromisso antes de qualquer ativação |

Os valores foram consultados nas páginas oficiais em 2026-10-27. São referências publicadas pelos fornecedores, sujeitas a mudança e às condições de cobrança aplicáveis à conta. Não foi feita uma estimativa de custo porque a infraestrutura e o volume de telemetria ainda não foram medidos.

## Decisão

Adotar New Relic como plataforma escolhida para observabilidade da Fase 3. A escolha considera a faixa gratuita publicada e a possibilidade de começar a avaliação sem custo de ingestão até o limite informado, o que é compatível com o escopo acadêmico atual. Essa adequação é uma hipótese para validar em HML, não uma garantia de que o plano permanecerá sem custo.

Antes de habilitar a integração:

1. conferir os limites, usuários e recursos incluídos no plano da conta;
2. definir uma política de ingestão e acompanhar o volume antes de habilitar novas fontes;
3. confirmar a cobertura das métricas do API Gateway REST e da AWS por meio das integrações configuradas;
4. manter os custos e o sinal de telemetria visíveis durante o teste em HML.

## Controles de dados

- CPF, CNPJ, tokens, cookies, senhas, headers de autorização e payloads de requisição não podem ser enviados como atributos de trace, logs, métricas ou tags.
- Chaves de ingestão ficam em secrets do ambiente de deploy; nunca entram em manifests, exemplos versionados ou imagens.
- A amostragem pode ser completa em HML para validação e ajustada em PRD conforme volume e plano.
- Eventos e métricas de negócio usam identificadores técnicos e dados agregados.

## Consequências e validação

- Integração de agente e APM para API, Lambda, Gateway e Kubernetes continua na issue #92.
- Logs JSON e correlation ID estão na issue #93; dashboards e alertas ficam na issue #94.
- A conclusão dessas issues deve demonstrar heartbeat, traces e métricas em HML, sem PII, além de confirmar cobertura do Gateway REST.
- O nome do fornecedor e a configuração de IaC não comprovam que a telemetria chega à plataforma.
- Reavaliar o plano e o custo antes de ativar fontes adicionais ou promover a configuração para PRD.

## Referências

- [New Relic pricing](https://newrelic.com/pricing)
- [New Relic Kubernetes integration](https://docs.newrelic.com/docs/kubernetes-pixie/kubernetes-integration/get-started/introduction-kubernetes-integration/)
- [New Relic AWS Lambda monitoring integration](https://docs.newrelic.com/docs/infrastructure/amazon-integrations/aws-integrations-list/aws-lambda-monitoring-integration/)
- [Datadog pricing](https://www.datadoghq.com/pricing/list/)
- [Issue #92: integração de observabilidade](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/issues/92)
