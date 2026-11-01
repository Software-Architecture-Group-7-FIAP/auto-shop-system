# New Relic HML service-order dashboard and alerts

## Dashboard contract

The private `HML Service Order Operations` dashboard reads the structured `Log`
events documented in [the service-order event contract](new-relic-service-order-events.md).
The records use `service = 'auto-shop-api'` and `environment = 'staging'`; the
application's staging deployment is the HML environment. All widgets include
those filters and `event_version = 1`.

| Panel | Window and unit | Interpretation |
| --- | --- | --- |
| Daily volume | 7 days; orders/day | Count of committed `ServiceOrderCreated` events per day. Delivery is best effort, so this is operational telemetry rather than an audit ledger. |
| Duration by status | 7 days; minutes | Average of completed `duration_ms` intervals, converted to minutes and faceted by `status`: `Em diagnóstico`, `Em execução`, or `Finalizada`. An open interval is not included. |
| Failures by type and subsystem | 24 hours; failures/hour | Counts `ServiceOrderProcessingFailure`, grouped by the closed `failure_type` and `subsystem` taxonomies. |

Current failure values are `processing_error` and `integration_error`; current
subsystems are `service_order` and `event_bus`. Use the event contract as the
source of truth if those taxonomies change.

The aggregate panels never select or facet by `service_order_id`, `event_id`,
`correlation_id`, `trace.id`, or `span.id`. They also exclude personal data,
credentials, and request or response contents. The notification message must
contain only severity, condition name, the constant service name
`auto-shop-api`, HML environment, UTC incident time, and this runbook link. Do
not include a dynamically selected entity name, record IDs, customer details,
or trace identifiers in alert payloads or notification links.

## Failure alert

The `Service-order processing failure` condition is a provisional critical
threshold: at least one failure event in a 300-second event-flow window, with a
120-second aggregation delay and no loss-of-signal alert. This pages on any
unexpected processing failure or EventBridge integration failure; expected
domain rejections are excluded by the event producer.

The logical notification route is `hml-sre-approved-workflow`, owned by the HML
SRE on-call. The provisioner creates or updates the private dashboard, policy,
and condition without attaching a notification destination. Before HML apply,
the SRE owner must confirm that the route and recipients are approved and that
the provisional threshold is appropriate. Attach a destination separately
through the approved New Relic workflow; keep its destination ID in the
runtime secret `NEW_RELIC_NOTIFICATION_DESTINATION_ID`, never in this repo.

## Trace an individual failure

Start with an alert or a failure count in the dashboard, then inspect a single
`ServiceOrderProcessingFailure` record in the restricted New Relic log view.
For example, query the recent event fields below and select one row:

```sql
FROM Log SELECT timestamp, trace.id, span.id, failure_type, subsystem
WHERE event = 'ServiceOrderProcessingFailure'
  AND event_version = 1
  AND service = 'auto-shop-api'
  AND environment = 'staging'
SINCE 30 minutes ago
```

When New Relic agent linking metadata is present, use that record's `trace.id`
or `span.id` to open the corresponding technical trace. A trace link can be
absent when the event was emitted outside a traced request or the agent did not
forward linking metadata. Keep these identifiers on the individual restricted
investigation record; never add them to a dashboard aggregate, alert query,
facet, notification payload, or public link.

## Controlled HML drill

The alert is not considered verified until a controlled failure has opened and
closed an incident in an active, signed HML lifecycle window. The checked-in
lifecycle gate ended at 23:00 BRT on 2026-10-31. A new signed token alone
cannot reopen it. Run this drill only after the project coordinator formally
reopens or extends HML through the approved review process, updates the
lifecycle gate, and issues an active signed session. Do not infer authorization
from an old session or bypass the lifecycle gate.

1. Confirm the HML SRE owner approved the route and the single-event threshold.
2. Use the existing approved fault-injection or controlled integration path to
   produce exactly one synthetic integration failure. Do not use real customer
   data or expose request contents.
3. Apply the service-order condition through the guarded HML workflow, then
   verify the incident opens within the evaluation window plus aggregation
   delay and reaches only the approved route.
4. Inspect the single failure event, verify the event taxonomy and available
   technical trace link, then resolve the synthetic failure and confirm that
   the incident closes.
5. Record the workflow URL, UTC start/end, sanitized incident timing, and
   whether trace linking was available. Do not record personal data, secrets,
   payloads, or record IDs.
6. Run the lifecycle teardown action before the authorized HML window ends.

If a safe approved integration fault-injection path is unavailable, stop and
record the drill as blocked; do not create a production-style failure by
mutating shared infrastructure or business data.

## Lifecycle teardown

Use the guarded workflow's `disable` action while the signed teardown window is
active. It disables only the explicitly owned condition and preserves the
dashboard for review. Confirm the condition is disabled before the HML
environment is stopped. The provisioner never attaches or removes unrelated
notification destinations.
