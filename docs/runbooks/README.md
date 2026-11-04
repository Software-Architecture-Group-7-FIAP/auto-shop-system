# Runbooks operacionais (#95)

Procedimentos para incidentes comuns e operação do ecossistema. Detalhes longos permanecem nos documentos linkados; este índice atende ao cenário 5 da [#95](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/issues/95).

| Situação | Runbook |
| --- | --- |
| Deploy, infra, rollback, falhas de Pod/RDS | [RUNBOOKS.md](../RUNBOOKS.md) (inglês — procedimentos gerais) |
| Deploy CD / OIDC / environments | [.github/CD.md](../../.github/CD.md) |
| Proteção de branches e checks obrigatórios | [.github/BRANCH_PROTECTION.md](../../.github/BRANCH_PROTECTION.md) |
| API indisponível / erro 5xx na borda | Verificar WAF + API Gateway ([ADR-0073](../architecture/decisions/ADR-0073-api-gateway-borda-publica.md)), Ingress e health do backend; logs com `correlation_id` (PR [#174](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/pull/174)) |
| Falha no processamento de OS (#67) | [new-relic-service-order-dashboard-alerts.md](../observability/new-relic-service-order-dashboard-alerts.md); evento `ServiceOrderProcessingFailed` |
| Rollback de deploy (imagem) | [RUNBOOKS.md](../RUNBOOKS.md) — seção troubleshooting; [k8s/scripts/deploy.sh](../../k8s/scripts/deploy.sh) |
| New Relic sem sinal / canária | [new-relic-hml-ingest.md](../observability/new-relic-hml-ingest.md) |
| Alertas técnicos (latência, erros) | [new-relic-technical-dashboard-alerts.md](../observability/new-relic-technical-dashboard-alerts.md) |

**Gate HML:** sessões AWS e deploy completo exigem staging demonstrável ([#87](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/issues/87)).
