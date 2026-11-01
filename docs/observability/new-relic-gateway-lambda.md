# New Relic telemetry for API Gateway and `lambda-auth`

## Sources and coverage

The selected source for API Gateway REST is New Relic AWS API polling over
CloudWatch `AWS/ApiGateway`. Terraform already enables detailed metrics for all
stage methods and keeps execution data tracing disabled. The five-minute polling
cycle reports `ApiGatewaySample` events; it is not a
request-level trace.

Expected API polling fields are `provider.count`, `provider.latency`,
`provider.integrationLatency`, `provider.4xxError` and `provider.5xxError`,
filterable by API, stage and—because detailed metrics are enabled—method and
resource. Confirm the live schema with `keyset()` before saving queries.

Native `AWS/Lambda` polling supplies invocations, errors, duration and
throttles. It does not prove cold starts. Cold starts and a safe per-invocation
correlation attribute require the separately owned instrumentation described
in [`lambda-auth-new-relic-handoff.md`](lambda-auth-new-relic-handoff.md).

## Persistent AWS account-link bootstrap

This linkage is persistent account bootstrap, not part of the ephemeral HML
lifecycle. Perform it only after separate infrastructure approval using the
New Relic onboarding-generated AWS principal and external ID. The trust policy
must require `sts:ExternalId`. `NEW_RELIC_LICENSE_KEY cannot configure` this
control-plane integration; do not substitute the ingest key for a New Relic
User API key.

Use a dedicated read-only policy limited to these actions:

- `cloudwatch:GetMetricData`, `cloudwatch:GetMetricStatistics`,
  `cloudwatch:ListMetrics`
- `apigateway:GET`
- `lambda:ListFunctions`, `lambda:GetFunctionConfiguration`, `lambda:ListTags`

Do not grant CloudWatch Logs read permissions. In particular, the integration
does not need log-event access. Scope `lambda:GetFunctionConfiguration` and
`lambda:ListTags` to the exact `lambda-auth-hml` ARN; use wildcard only for the
list operation that cannot be resource-scoped. Scope API Gateway reads to the
owned REST API wherever AWS IAM supports it. Verify the effective policy before
linking, and verify that the Lambda environment contains no credentials or
secrets readable through function configuration. Keep the generated external
ID in the approved secret/control-plane mechanism and never place User API keys
in Terraform, tfvars, workflow arguments, output, state artifacts or logs.
Remove the linked account and IAM role together if this integration is
decommissioned.

## Controlled HML correlation

The manual authentication workflow sends exactly one request with a synthetic
CPF sourced from the `hml` Environment secret. The identity owner must attest
that it is a dedicated generated non-person test record, never a real customer,
and must remove the secret when the test identity is retired. It accepts only the fixed HML
HTTPS endpoint, rejects redirects, uses a ten-second timeout, and discards the
response body and JWT. It emits only HTTP status, API Gateway request ID and an
opaque UUID.

Run it only in an approved HML session after the `lambda-auth` privacy contract
is deployed. Correlate the UUID with the instrumented Lambda transaction, then
compare the bounded UTC window with aggregate Gateway and Lambda metrics. API
polling cannot associate one Gateway metric point with one invocation, so this
is temporal/aggregate correlation, not an end-to-end Gateway trace.

Example discovery queries after the account link is active:

```sql
FROM ApiGatewaySample
SELECT sum(provider.count), average(provider.latency),
       sum(provider.4xxError), sum(provider.5xxError)
WHERE stage = 'hml'
FACET apiName, resource, method
SINCE 15 minutes ago

FROM ServerlessSample
SELECT sum(provider.invocations), sum(provider.errors),
       average(provider.duration), sum(provider.throttles)
WHERE provider.functionName = 'lambda-auth-hml'
SINCE 15 minutes ago

FROM Span
SELECT count(*)
WHERE service.name = 'lambda-auth-hml'
  AND observability.run_id = '<workflow UUID>'
SINCE 15 minutes ago
```

The exact Lambda event type and provider attribute names can vary by New Relic
integration generation. Inspect the live schema before treating these examples
as saved queries. Evidence must record the approved session, UTC window,
workflow run, safe UUID, entity names and non-sensitive result counts. Never
capture screenshots containing CPF, CNPJ, JWT, cookies, Authorization headers,
request bodies or response bodies.

As of 2026-11-01, the repository's authorized HML operation window ended on
2026-10-31. The workflow must remain fail-closed until the lifecycle owner
grants a new signed window through the existing validator; do not weaken or
bypass that gate for observability evidence.
