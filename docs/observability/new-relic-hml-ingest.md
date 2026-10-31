# New Relic HML ingestion canary

## Current state

The project selected New Relic in [ADR-0078](../architecture/decisions/ADR-0078-observabilidade-new-relic.md). On 2026-10-31, the account owner confirmed the Free plan and United States data region. The official [Free tier page](https://newrelic.com/pricing/free-tier) lists 100 GB of ingest per month, one Full Platform user, unlimited Basic users, at least 8 days of default retention, and 500 synthetic checks. These are the published plan allowances; check actual account usage before sending telemetry, and do not treat the monthly allowance as a per-canary cost cap.

The HML GitHub Environment now contains the environment secret `NEW_RELIC_LICENSE_KEY`; its name was verified and its value was not read back. The canary is implemented locally but has not been sent to New Relic. The workflow is not yet present on `develop`, while the `hml` Environment allows only `develop`, so it cannot be dispatched until the implementation is reviewed and promoted through the project workflow. The repository's default branch is `main`; GitHub only offers `workflow_dispatch` for a workflow present on that default branch. A separate, minimal promotion must register this workflow on `main`, after the feature has been merged to `develop`; the dispatch must then target `develop` so the HML environment restriction and implementation match. Do not merge all of `develop` into `main` just to register the workflow: those branches have diverged. See [GitHub's manual workflow dispatch requirements](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow). Do not put the key value in this repository, a manifest, Terraform, an image, an issue comment, or a log. The workflow grants no AWS identity and does not create AWS resources.

For the confirmed United States data region, New Relic's OTLP/HTTP endpoint is `https://otlp.nr-data.net`; New Relic requires the license key in the `api-key` header. See the [official OTLP endpoint documentation](https://docs.newrelic.com/docs/opentelemetry/best-practices/opentelemetry-otlp/).

The latest [HML opening run #12](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/actions/runs/41226878721) passed its HML gates and cost preflight, then failed during “Plan the K8s foundation opening”; its apply and bootstrap steps did not run. It does not establish an active approved HML session. No New Relic canary has been sent.

## Why Issue 01 remains open

This change delivers the bounded New Relic sender, its develop-only manual workflow, secret wiring, and tests. One workflow-promotion step remains in addition to live verification: `main` is the default branch, so the manual Actions entry point must also be registered there in a small, separate promotion. The HML Environment is restricted to `develop`, and `main` and `develop` have diverged, so a broad branch merge is not an acceptable shortcut. Even after both promotions, the change does not satisfy the live-ingestion acceptance criteria by itself. HML opening run #12 failed before apply/bootstrap, and its annotation reports that the correlated run also failed. The underlying plan failure has not been diagnosed, so there is no evidence of a currently approved active HML session. The account's actual remaining ingest usage has also not been checked.

After this PR is merged to `develop`, register the workflow on default branch `main` through an isolated PR, then choose `develop` as the run ref. Resume Issue 01 by diagnosing the HML foundation-plan failure and opening a session through the existing authorized lifecycle process. Check the account's remaining ingest allowance, dispatch the canary once during that approved session, and query New Relic for the run ID. Keep Issue 01 open until the metric is visible and the query result is recorded; merging this code is not live-ingestion evidence.

## Bounded signal and trigger

`.github/workflows/new-relic-hml-canary.yml` accepts only a manual dispatch from `develop`, requires explicit confirmation that ingestion is intended, and reuses the signed HML session validation used by the staging deployment workflow. It sends one OTLP metric point and has no schedule, push trigger, retry loop, or background agent.

The request contains only these attributes:

- Resource: `service.name=auto-shop-ingest-canary` and `deployment.environment=hml`.
- Metric: one gauge point named `auto_shop_new_relic_ingest_canary`, with value `1`.
- Data point: `canary.run_id`, generated from the GitHub workflow run.

The request body is capped at 2 KiB. The operational volume guardrail is one manual run per approved HML session, followed by a New Relic query before any additional source is enabled. Do not repeat the dispatch to troubleshoot an uncertain result; inspect the workflow result and query the run ID first. The real account's ingest allowance and usage must be checked before dispatch.

## Secret and account setup

1. Plan and region were confirmed by the account owner on 2026-10-31: Free plan, United States region.
2. The New Relic license key is stored in GitHub Environment `hml` as `NEW_RELIC_LICENSE_KEY`. Do not use a user API key for OTLP ingestion.
3. The `hml` Environment is restricted to `develop`; the staging session variables are present. The latest HML opening attempt failed before apply/bootstrap, so wait for a separately approved, active session.
4. After the workflow is present on default branch `main` and the matching implementation is on `develop`, choose `develop` in the workflow's branch selector. During an approved HML session, dispatch **New Relic HML ingest canary**, select `us`, provide the coordinator session inputs, and set `confirm_hml_ingestion` to `true` once.

The script sends the key only in the OTLP `api-key` HTTP header over HTTPS and rejects redirects so the header cannot be forwarded to another host. It does not print the key or the response body. The workflow's HTTP 200 result confirms the endpoint acknowledged the request; it does not prove the data is queryable.

## Arrival verification

Copy `canary_run_id` from the workflow summary and run:

```sql
FROM Metric
SELECT latest(auto_shop_new_relic_ingest_canary)
WHERE service.name = 'auto-shop-ingest-canary'
  AND deployment.environment = 'hml'
  AND canary.run_id = '<canary_run_id>'
SINCE 30 minutes ago
```

Record the account edition/limits, confirmed region, run URL and ID, query timestamp, and returned value in the issue evidence. If the query returns no point, stop and inspect the New Relic OTLP integration errors before sending another request.

## AWS and API Gateway REST coverage

New Relic documents API Gateway REST (v1) metrics through either CloudWatch Metric Streams or its API polling integration. The documented metrics include `4XXError`, `5XXError`, `CacheHitCount`, `CacheMissCount`, `Count`, `IntegrationLatency`, and `Latency`. Per-resource call and error metrics require detailed CloudWatch metrics; enabling them may add AWS charges. New Relic recommends Metric Streams for AWS metric collection, but that path provisions CloudWatch Metric Streams and Kinesis Data Firehose resources and is outside this canary.

`infra/aws/api_gateway.tf` currently configures `metrics_enabled = true` for all stage methods (`method_path = "*/*"`), so the desired Terraform state requests detailed method/resource metrics. That setting may add CloudWatch charges. A read-only AWS inspection on 2026-10-31 in `us-east-1` found the staging VPC, EKS cluster, RDS instance, two running worker nodes, and lifecycle DynamoDB table; it found no API Gateway REST APIs, CloudWatch Metric Streams, or Firehose streams. This conflicts with ADR-0071's Oct 29 note that staging resources are inactive. Reconcile the live inventory and ADR before relying on either as the deployment state. The API Gateway access logs are a separate data source and are not part of this canary or the proposed metric stream.

The project has not enabled or live-verified either New Relic AWS integration path, and this issue does not enable additional AWS sources. Before that work, confirm ownership with `k8s-infra`, estimate the CloudWatch/Firehose costs, verify whether detailed metrics are needed for the chosen queries, and follow ADR-0064's specific authorization gate for AWS changes.

## References

- [New Relic OTLP endpoint and license-key header](https://docs.newrelic.com/docs/opentelemetry/best-practices/opentelemetry-otlp/)
- [OpenTelemetry metrics protocol definition](https://github.com/open-telemetry/opentelemetry-proto/blob/main/opentelemetry/proto/metrics/v1/metrics.proto) and [metrics export request](https://github.com/open-telemetry/opentelemetry-proto/blob/main/opentelemetry/proto/collector/metrics/v1/metrics_service.proto)
- [New Relic API Gateway REST (v1) monitoring coverage](https://docs.newrelic.com/docs/infrastructure/amazon-integrations/aws-integrations-list/aws-api-gateway-v1-monitoring-integration/)
- [New Relic AWS integrations](https://docs.newrelic.com/docs/infrastructure/amazon-integrations/get-started/introduction-aws-integrations/)
- [New Relic Free tier pricing and allowances](https://newrelic.com/pricing/free-tier)
