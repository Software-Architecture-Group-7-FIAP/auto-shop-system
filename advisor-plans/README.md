# Fase 3 — documentos por responsabilidade

Os documentos abaixo detalham a execução por pessoa da divisão original. Na equipe atual, **Gustavo assume as Pessoas 1 e 2** e **o outro desenvolvedor assume a Pessoa 3**. O estado de implementação é o retrato da auditoria de 22/10/2026; a separação documental não representa uma nova verificação dos ambientes.

## Documentos principais

| Documento | Responsável atual | Conteúdo |
| --- | --- | --- |
| [Pessoa 1 — identidade e integração](fase-3-pessoa-1-identidade-e-integracao.md) | Gustavo | Status, CPF, JWT/JWKS, autorização da OS, produtor de eventos e homologação #63–#68. |
| [Pessoa 2 — guia de implementação de plataforma e CI/CD](guia-implementacao-pessoa-2.md) | Gustavo | Sequência atualizada das issues `database-infra#1–#6`, `k8s-infra#1–#11` e integração `auto-shop-system#85/#87`, alinhada ao ADR-0071. |
| [Pessoa 3 — observabilidade e entrega](fase-3-pessoa-3-observabilidade-e-entrega.md) | Outro desenvolvedor | Logs, traces, dashboards, alertas, consumidor de notificações, documentação, vídeo e PDF #92–#95. |

São documentos de situação e execução, com decisões arquiteturais existentes referenciadas. Decisões ainda em aberto permanecem propostas; estes documentos não atribuem aprovação a escolhas não confirmadas nem substituem os ADRs existentes.

O [plano de Pessoa 2 anterior](fase-3-pessoa-2-plataforma-e-cicd.md) preserva a auditoria de situação com data-base 22/10/2026; use o novo guia para a sequência vigente e a distribuição atual das issues.

## Ordem de integração

1. Pessoa 1 fornece os contratos de JWT, endpoints e eventos; Pessoa 2 consolida repositórios, contratos de infraestrutura e ambientes.
2. Pessoa 2 entrega rede, cluster, banco, secrets, Gateway e deploy; Pessoa 3 avança em instrumentação, consumidor e documentação em paralelo.
3. Pessoas 1 e 2 validam #68/#87; Pessoa 3 comprova observabilidade e notificações no mesmo ambiente.
4. Ambos revisam as evidências; Pessoa 3 consolida documentação e pacote final.

## Relatório consolidado de origem

| Documento | Base | Estado |
| --- | --- | --- |
| [Fase 3 — situação e divisão para dois desenvolvedores](relatorio-fase-3-status-e-divisao-2-devs.md) | Código local e GitHub consultados em 22/10/2026; aplicação `develop/9009a18b`, Lambda `main/5a75c5d` | Análise concluída; implementação e homologação pendentes conforme matriz. |

O relatório consolidado permanece como registro da análise original. Os três documentos são a referência de execução por responsabilidade. Esta pasta mantém esse material separado do plano anterior em `plans/`; os critérios de aceite das issues existentes continuam aplicáveis.
