# Service-order business telemetry

This contract exposes aggregate service-order throughput, completed status
durations, and operational failures through the structured `Log` records already
forwarded to New Relic. It does not call a New Relic API from business code.

## Event contract

All timestamps are UTC ISO 8601 values. Event schemas are versioned with
`event_version=1`. Success events are queued with the database transaction and
are emitted only after a successful commit; rollback discards them. Delivery to
New Relic remains best effort and never changes the business result.

### `ServiceOrderCreated`

Emitted once when a new OS row is committed. Idempotent approval and budget
revision paths do not emit another event.

Allowed business fields: `event`, `event_version`, `occurred_at`, and `status`.

### `ServiceOrderStatusDuration`

Emitted for a committed transition where `from_status != to_status`. Same-status
audit actions such as queueing and mechanic reassignment are excluded.

Allowed business fields: `event`, `event_version`, `occurred_at`, `status`,
`to_status`, `transition_type`, `duration_ms`, and
`duration_unit=milliseconds`. `duration_ms` is the completed interval between
the persisted entry into `status` and the next real transition. Re-entry creates
a separate completed interval. Negative, open, unknown, or longer-than-ten-year
intervals are discarded.

### `ServiceOrderProcessingFailure`

Emitted for unexpected processing failures and failure of the EventBridge
integration. Expected validation and business rejections use
`service_order_domain_rejection` and are intentionally excluded from failure
rates.

Allowed business fields: `event`, `event_version`, server-generated `event_id`,
`occurred_at`, `failure_type`, `subsystem`, and `service_order_id`.
`failure_type` and `subsystem` are closed taxonomies. The sequential OS ID is
allowed only on failure records for restricted operational investigation; it
must not be used as a dashboard facet or metric dimension.

The final structured-log envelope adds `timestamp`, `level`, the constant
`message=service_order_business_event`, `logger`, `service`, `environment`, and
`version`. It may also add New Relic agent-produced `trace.id`/`span.id`.
Business events explicitly suppress ambient `correlation_id` and ambient OS IDs;
only failure events carry the OS ID supplied by their typed contract.

## Privacy boundary

The event builders use a strict allowlist. They never receive or emit CPF, CNPJ,
customer or mechanic names, email, phone, address, customer/vehicle/budget/actor
IDs, price, free-text reason, diagnostic text, exception details, stack traces,
credentials, JWT, cookies, headers, URL/query data, or request/response payloads.

Access to failure records must be restricted to operators, with the shortest
retention supported by the approved New Relic account policy. Never facet by
`event_id`, `service_order_id`, trace ID, or span ID.

## NRQL examples

Daily committed OS volume (calendar-day interpretation uses the New Relic
account timezone):

```sql
FROM Log SELECT count(*)
WHERE event = 'ServiceOrderCreated' AND event_version = 1
SINCE 7 days ago TIMESERIES 1 day
```

Average completed duration by status, in milliseconds, over a rolling 7-day
window:

```sql
FROM Log SELECT average(duration_ms)
WHERE event = 'ServiceOrderStatusDuration'
  AND event_version = 1
  AND status IN ('Em diagnóstico', 'Em execução', 'Finalizada')
SINCE 7 days ago FACET status
```

Processing and integration failures over a rolling 24-hour window:

```sql
FROM Log SELECT count(*)
WHERE event = 'ServiceOrderProcessingFailure' AND event_version = 1
SINCE 24 hours ago FACET failure_type, subsystem
```

For investigation, open a single failure record and follow its `trace.id` or
`span.id`. Do not add those identifiers to aggregate queries.

## Coverage and validation

Business events are not sampled by application code. Delivery is process-local
and best effort after commit, so a process crash between database commit and log
forwarding can lose a signal; dashboards must not be treated as an audit ledger.
New Relic account-level
retention, ingest limits, or sampling can still create gaps and must be recorded
with dashboard evidence. HML validation requires a new signed lifecycle window;
the prior window ended on 2026-10-31 and must not be bypassed.
