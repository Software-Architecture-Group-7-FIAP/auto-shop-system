# Observabilidade — índice (#92, #93, #94)

Decisão de fornecedor: [ADR-0078](../architecture/decisions/ADR-0078-observabilidade-new-relic.md) (New Relic). RFC de apoio: [RFC-0004](../rfc/RFC-0004-observabilidade-new-relic.md).

## Documentos por componente

| Tema | Documento |
| --- | --- |
| Logs JSON + correlation ID (backend) | Implementação na base `develop`; propagação e2e na [PR #174](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/pull/174) (`correlation-id-propagation.md`) |
| FastAPI APM (`auto-shop-api`) | [new-relic-fastapi-apm.md](./new-relic-fastapi-apm.md) |
| Kubernetes (Pods, CPU/mem) | [new-relic-kubernetes.md](./new-relic-kubernetes.md) |
| API Gateway + Lambda (`auto-shop-auth-lambda`) | [new-relic-gateway-lambda.md](./new-relic-gateway-lambda.md), [lambda-auth-new-relic-handoff.md](./lambda-auth-new-relic-handoff.md) |
| Ingestão canária HML (OTLP) | [new-relic-hml-ingest.md](./new-relic-hml-ingest.md) |
| Eventos de OS / falha (#67) | [new-relic-service-order-events.md](./new-relic-service-order-events.md) |
| Dashboards e alertas (técnico + OS) | [new-relic-technical-dashboard-alerts.md](./new-relic-technical-dashboard-alerts.md), [new-relic-service-order-dashboard-alerts.md](./new-relic-service-order-dashboard-alerts.md) |

Runbooks operacionais: [docs/runbooks/README.md](../runbooks/README.md).

## Checklist — critérios de aceite da [#92](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/issues/92)

Status até a documentação e HML estarem validados em sessão autorizada ([#87](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/issues/87)).

| Cenário | Estado | Onde validar / evidência |
| --- | --- | --- |
| **1** Conta e agente provisionados | Preparado; heartbeat pendente | Plano Free US documentado em ADR-0078; bundle K8s em `k8s-infra`; canária em [new-relic-hml-ingest.md](./new-relic-hml-ingest.md) |
| **2** APM no backend | Preparado; traces pendentes | [new-relic-fastapi-apm.md](./new-relic-fastapi-apm.md); service name `auto-shop-api` |
| **3** Integração Kubernetes | Preparado; métricas pendentes | [new-relic-kubernetes.md](./new-relic-kubernetes.md) |
| **4** Gateway / Lambda | Preparado; painéis pendentes | [new-relic-gateway-lambda.md](./new-relic-gateway-lambda.md) |
| **5** Secrets no CI/CD | Parcialmente ativo | `NEW_RELIC_LICENSE_KEY` no Environment `hml`; nunca em repo — ver [.github/CD.md](../../.github/CD.md) |

**Regras:** sem PII (CPF/CNPJ/tokens) em tags ou atributos; amostragem 100% em HML conforme ADR-0078.

A issue **#92** permanece aberta até heartbeat, traces e métricas com evidência em HML. A **#94** depende dos mesmos dados para dashboards/alertas “vivos”.
