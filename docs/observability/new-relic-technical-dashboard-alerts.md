# New Relic HML technical dashboard and alerts

The owned dashboard is `auto-shop-owned::HML Technical Health`; the owned alert
policy is `auto-shop-owned::HML Technical Alerts`. Their checked-in definitions
are under `observability/new-relic/`. Provisioning uses NerdGraph variables and
an approved User API key. It never uses the New Relic ingest/license key.

## Dashboard contract

The default panel window is the rolling last 30 minutes. Every saved query is
aggregate-only. The FastAPI APM entity is `appName='auto-shop-api'`. The Python
agent label is `environment:hml`, while sanitized application logs use
`environment='staging'`; these are intentional contracts and must not be merged
into one assumed value.

| Panel | Source | Unit | Fixed filters | Coverage note |
|---|---|---|---|---|
| FastAPI throughput | `Transaction` | requests/minute | `appName='auto-shop-api'`, `label.environment='hml'` | APM transactions only |
| FastAPI availability/error rate | `Transaction` | percent | same app | no traffic means no data, not 100% |
| FastAPI latency | `Transaction` | seconds | same app | p50/p95/p99 |
| Gateway volume/errors | `ApiGatewaySample` | count/5-minute poll | `stage='hml'` | aggregate polling, not traces |
| Gateway availability/error rate | `ApiGatewaySample` | percent | `stage='hml'` | availability excludes 4xx and is `100 × (Count − 5XXError) / Count`; zero requests produce no availability claim |
| Gateway latency | `ApiGatewaySample` | milliseconds | `stage='hml'` | verify provider fields and unit live |
| lambda-auth health | `ServerlessSample` | count/milliseconds | `provider.functionName='lambda-auth-hml'` | cold starts omitted until instrumentation is verified |
| Kubernetes pod resources | `K8sPodSample` | cores/bytes | cluster and namespace `auto-shop-hml` | absolute usage, not percentage of limit |
| Kubernetes readiness | `K8sPodSample` | pods | same cluster/namespace | unique non-ready pod count |
| Kubernetes restarts | `K8sContainerSample` | cumulative restarts | same cluster/namespace | faceted; counters are never summed across containers |
| HPA replicas | `K8sHpaSample` | replicas | same cluster/namespace | current versus desired |

The manifest records source, range, unit, filters and a coverage note per panel.
Panel titles and queries repeat the operational unit/filter so the dashboard
does not depend on this document alone.

## AWS schema gate

API Gateway and Lambda provider field names can vary between New Relic AWS
integration generations. Before the first apply, use a signed active HML window
to run bounded `keyset()` discovery for `ApiGatewaySample` and the Lambda sample
type, and confirm `label.environment='hml'` on the APM `Transaction` entity.
The Gateway availability panel derives a success rate from `Count` and
`5XXError`, and shows `4XXError` and `5XXError` rates separately. Treat those
provider mappings as unverified until the signed-window schema discovery
confirms the exact attributes and units.
Record only attribute names, counts, UTC time and the workflow run URL.
Do not record raw events.

After confirming the checked-in fields and units, set
`aws_schema_mapping.verified=true`, `verified_at` to the UTC evidence time, and
`evidence_run_url` to the authorized run. The reconciler refuses `apply` without
both that checked-in evidence and `--confirm-aws-schema`. `disable` intentionally
remains available through the signed teardown action when schema evidence is unavailable.
Cold-start coverage must remain absent until the separately owned `lambda-auth`
agent produces a verified safe attribute.

## Alert policy

Thresholds are initial HML values and require tuning from sanitized baseline
evidence. All conditions use `fillOption=NONE`; loss-of-signal incidents are
disabled because HML is intentionally ephemeral.

### API availability

- Critical: availability below 95% for 10 minutes.
- Evaluation: 5-minute event-flow windows with 120-second delay, all windows.
- Limitation: low traffic can make percentages noisy; no traffic is no data.

### API latency and errors

- Latency warning: p95 above 1 second for 15 minutes.
- Latency critical: p95 above 2 seconds for 10 minutes.
- Error warning: above 5% for 15 minutes.
- Error critical: above 10% for 10 minutes.
- Evaluation: 5-minute event-flow windows with 120-second delay.

### Kubernetes health

- Critical readiness: at least one non-ready pod for 5 minutes.
- Warning restart increase: `max(restartCount)-min(restartCount)` per pod and
  container at least 3 for 10 minutes. Raw cumulative restart count is not the
  alert threshold.
- Warning CPU: pod usage above 0.85 cores for 15 minutes.
- Warning memory: pod working set above 768 MiB for 15 minutes.

CPU and memory are intentionally separate because their units differ. They are
absolute provisional thresholds, not fabricated percentages of resource limit.

## Notification route

The logical route is `hml-sre-approved-workflow`, owned by the HML SRE on-call.
The destination/workflow is provisioned and approved separately in New Relic;
no email, webhook, Slack/Teams URL, destination GUID or credential is versioned
here. `apply` requires an explicit confirmation that recipient ownership is
current, but the reconciler does not create or silently attach a destination.
Attach the owned policy to the approved workflow only after the separate route
review. Scope its filter to the exact owned policy/condition IDs.

Notification templates may include only severity, condition/entity display
name, `hml`, UTC time and this runbook URL. Never include query samples, logs,
payloads, OS/customer IDs, trace/correlation IDs, headers or exceptions.

## Provisioning workflow

Use `.github/workflows/new-relic-hml-technical.yml` from `develop`. Operations:

- `validate`: local schema/privacy validation; no New Relic secret is exposed.
- `plan`: read-only discovery of the exact owned names.
- `apply`: create/update the owned dashboard, policy and seven conditions.
- `disable`: disable only the seven exact owned conditions before HML teardown.

The workflow requires the signed lifecycle capability, active HML environment,
protected `hml` GitHub Environment, explicit confirmations and a protected
`NEW_RELIC_USER_API_KEY`. The key exists only in the single NerdGraph step and
is removed immediately. The account ID is supplied through the protected
`NEW_RELIC_ACCOUNT_ID` environment variable. GraphQL documents are constants;
all values are variables. Redirects are rejected, responses are capped at 1 MiB
and error bodies are never printed.

Owned names use the `auto-shop-owned::` marker. Ambiguous discovery fails
closed. The reconciler never deletes resources and never updates a condition
outside the exact owned policy/name set.

## Controlled drills and evidence

Run drills only inside a new signed HML window. First use the New Relic channel
test capability against the separately approved destination. Sending a test
notification is an external side effect and requires explicit route-owner
approval.

For a readiness drill, use a short-lived isolated canary workload with a safe
technical label and a temporary copy of the condition scoped only to that
canary. For API drills, use a bounded synthetic custom signal and a temporary
condition. Do not lower canonical thresholds, generate customer-path failures,
stop the application, or log request/response data. Remove temporary conditions
and canary resources, then rerun `plan` to prove the canonical resource count is
unchanged.

Record the authorized run URL/session, UTC window, owned dashboard/policy and
condition GUIDs, sanitized panel result counts, incident open/close times,
notification delivery ID (never destination metadata), cleanup result and a
second idempotency plan. Inspect screenshots for personal data and credentials.

## Lifecycle teardown

Run `disable` before the environment-stop workflow destroys HML. Because
loss-of-signal is disabled, an intentional shutdown cannot open a no-data
incident, but disabling conditions also prevents stale late-arriving metrics
from paging. If disable fails, stop the teardown and have the route owner mute
the exact owned policy before continuing.

As of 2026-11-01, the previous authorized HML window ended on 2026-10-31. Do
not bypass the lifecycle validator to provision, drill, notify or disable.
