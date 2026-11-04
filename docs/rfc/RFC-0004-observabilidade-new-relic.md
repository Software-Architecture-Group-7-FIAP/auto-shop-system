# RFC-0004: Plataforma de observabilidade (New Relic)

- **Status:** aceita como direção arquitetural
- **Data:** 2026-11-02
- **Decisão relacionada:** [ADR-0078](../architecture/decisions/ADR-0078-observabilidade-new-relic.md)
- **Issues:** [#92](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/issues/92), [#94](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/issues/94)

## Resumo

Centralizar métricas, logs, traces e alertas da Fase 3 em **New Relic**, após comparação publicada com Datadog no ADR-0078. Este RFC descreve o escopo operacional; a instrumentação e evidências em HML ficam na issue #92.

## Escopo

| Camada | Service naming sugerido | Documentação |
| --- | --- | --- |
| FastAPI | `auto-shop-api` | [new-relic-fastapi-apm.md](../observability/new-relic-fastapi-apm.md) |
| Lambda auth | `auto-shop-auth-lambda` | [new-relic-gateway-lambda.md](../observability/new-relic-gateway-lambda.md) |
| API Gateway | integração AWS / métricas | idem |
| Kubernetes | infra + workloads | [new-relic-kubernetes.md](../observability/new-relic-kubernetes.md) |

Logs estruturados e `correlation_id` são tratados na [#93](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/issues/93), independentemente do agente APM.

## Controles

- Proibido enviar CPF, CNPJ, tokens ou payloads sensíveis como atributos de trace ou tags.
- License keys apenas em GitHub Environments / Kubernetes Secrets.
- Ingestão limitada e monitorada em HML (canária documentada antes de fontes adicionais).

## Consequências

- Dashboards e alertas (#94) usam NRQL e workflows descritos em `docs/observability/`.
- Fechamento da #92 exige ambiente HML ativo ([#87](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/issues/87)) e evidência de heartbeat/traces.

## Referências

- [Índice observabilidade](../observability/README.md)
- [ADR-0078](../architecture/decisions/ADR-0078-observabilidade-new-relic.md)
