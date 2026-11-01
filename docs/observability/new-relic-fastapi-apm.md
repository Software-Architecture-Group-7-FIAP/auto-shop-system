# New Relic FastAPI APM in HML

The HML backend runs under `newrelic-admin run-program`, so the Python agent is
initialized before FastAPI and the SQLAlchemy engine are imported. Telemetry is
reported as application `auto-shop-api` with the label `environment:hml`. Every
application JSON log includes the immutable image reference in `version`, the
request `correlation_id`, and `trace.id`/`span.id` when a New Relic transaction
is active.

The agent is disabled in the base Kubernetes configuration and enabled only by
the HML overlay. The HML GitHub Environment secret `NEW_RELIC_LICENSE_KEY` is
streamed into the dedicated `auto-shop-new-relic` Kubernetes Secret during an
authorized deployment. The value is not stored in a manifest, command-line
argument, image, or workflow output.

## Ingestion guardrail

HML uses New Relic's adaptive distributed-trace sampling. The agent's Python
logging import hook is disabled because it runs before application redaction. A
dedicated application handler forwards only the sanitized JSON; log-event
forwarding remains enabled for that explicit API call, and the agent's
log-event harvest remains capped at 1,000 records per minute per instance. Health
probes do not emit application access logs. Before an HML session, confirm the
remaining account ingestion allowance described in
[`new-relic-hml-ingest.md`](new-relic-hml-ingest.md); do not enable additional
telemetry sources as part of this validation.

The configuration disables request parameters, request/response headers, and
SQL statement recording. The application never logs request/response bodies.
Access logs use the FastAPI route template instead of concrete path parameters.
The JSON formatter also redacts CPF, CNPJ, bearer/JWT values, passwords, tokens,
cookies, sessions, and database URL credentials before forwarding.

## HML verification

During an approved active HML session, send a synthetic request with a unique,
non-sensitive correlation ID to a route that performs a database lookup. For
example:

```text
X-Correlation-ID: nr-apm-<GitHub run id>
```

Find the access log:

```sql
FROM Log
SELECT timestamp, level, service, environment, version, correlation_id,
       trace.id, span.id, path
WHERE service = 'auto-shop-api'
  AND environment = 'staging'
  AND correlation_id = 'nr-apm-<GitHub run id>'
SINCE 30 minutes ago
```

Open the related trace through `trace.id` and confirm that it contains the
normalized request route and datastore spans. Inspect the trace and log
attributes to verify that no document, credential, cookie, body, concrete path
identifier, SQL statement, or SQL bind value was exported. Record the run URL,
correlation ID, trace ID, query time, and observed ingest volume as the live HML
evidence; HTTP success or merged configuration alone is not that evidence.

## Local verification

The agent remains disabled locally. The application still emits the same JSON
schema, omitting `trace.id` and `span.id` when no active agent transaction
exists. This keeps local development independent of a New Relic key.
