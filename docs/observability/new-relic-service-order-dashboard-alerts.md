# New Relic HML service-order dashboard and alerts

## Dashboard contract

The replacement private dashboard is
`auto-shop-owned::HML Service Order Operations v2`. It reads the structured
`Log` events documented in [the service-order event contract](new-relic-service-order-events.md).
It uses the existing `auto-shop.ownership` tag key with a v2 ownership value;
the legacy v1 dashboard is retained and is not deleted by reconciliation.
The existing service-order alert policy and condition definitions are retained;
their manifest ownership marker moves to v2 with the replacement dashboard.
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

The drill is operator-led. This workflow never generates a failure, attaches a
notification destination, queries live logs or incidents, or resolves an
incident. It records only sanitized operator attestations after the live checks
and cleanup are complete. Do not call the drill successful from a workflow
summary alone.

The checked-in lifecycle validator currently authorizes HML only through
2026-11-05 23:00 BRT. Every dispatch still requires an active signed HML
session, coordinator authorization, the `develop` branch, and the protected
`hml` GitHub environment. A date or an old token does not authorize a run.
Changes to that lifecycle gate must follow the approved coordinator review;
never bypass it for this drill.

### Preconditions

- The HML SRE owner approves the provisional single-event threshold and the
  exact notification route and recipients.
- An already-approved HML integration fault-injection path is available. It
  must produce exactly one synthetic `ServiceOrderProcessingFailure` from test
  context without real customer data, shared-infrastructure disruption, or
  request/response capture. This repository does not provide or invoke that
  injector. If the owner cannot identify and approve the path, stop and record
  the drill as blocked; do not improvise an API call or induce an outage.
- The event schema is deployed and its allowlist and trace-follow-up rules in
  [the event contract](new-relic-service-order-events.md) have been reviewed.
- No service-order failure incident is already open. A baseline query over the
  ten minutes before the drill event returns zero. Start that full baseline
  interval after the signed HML session begins.

### Operator sequence

1. Ask the coordinator to open the HML window and issue the session ID, UTC
   `started_at`, and signed session token. Dispatch this workflow from
   `develop` with `session_mode=hml`, the active session values, and the account
   region. First run `validate`, then `plan`; save both workflow URLs. `plan`
   must show only the owned dashboard, policy, and single service-order
   condition. It must report notifications as not attached.
2. Run `apply` with `confirm_apply`, `confirm_business_telemetry`,
   `confirm_failure_threshold`, and `confirm_notification_route` checked. The
   confirmation attests that the owner approved the route; it does not attach
   it. Verify the dashboard is private and the owned condition has the one-event
   threshold, 300-second window, 120-second delay, and HML service filters.
3. Through the separately approved New Relic notification workflow, manually
   attach only `hml-sre-approved-workflow` to the owned service-order policy.
   Confirm the on-call recipients and route are correct. Do not enter a
   destination ID in GitHub or this repository.
4. In New Relic Logs, run a baseline count in the ten-minute period immediately
   before the injection. It must be zero. Use the Query builder, not a dashboard
   widget whose time picker could override the explicit range. Replace the
   bracketed placeholders below with UTC epoch milliseconds; New Relic documents
   those bounds in its [NRQL time-range reference](https://docs.newrelic.com/docs/nrql/using-nrql/query-time-range/).

   ```sql
   FROM Log SELECT count(*)
   WHERE event = 'ServiceOrderProcessingFailure'
     AND event_version = 1
     AND service = 'auto-shop-api'
     AND environment = 'staging'
   SINCE <baseline_start_epoch_ms> UNTIL <drill_start_epoch_ms>
   ```

5. Using only the pre-approved synthetic HML integration path from the
   preconditions, trigger it once. Do not retry. Record the UTC event time. Run
   this count query for a bounded interval that contains the event and the
   incident close; it must return exactly one. Do not widen the window to hide
   duplicates.

   ```sql
   FROM Log SELECT count(*)
   WHERE event = 'ServiceOrderProcessingFailure'
     AND event_version = 1
     AND service = 'auto-shop-api'
     AND environment = 'staging'
   SINCE <drill_start_epoch_ms> UNTIL <drill_end_epoch_ms>
   ```

   Inspect the dashboard's failure panel and confirm it reflects that one
   event. The condition should open an incident within its 300-second
   evaluation window plus the 120-second aggregation delay. Confirm the incident
   reached only the approved route. If the count is not one, another route is
   notified, or the incident does not open, do not retry; proceed to cleanup and
   mark the drill blocked.
6. Inspect the single restricted log row with the event type, timestamp,
   `failure_type`, `subsystem`, and available `trace.id`/`span.id`. Verify the
   taxonomy and follow an available trace link to its technical trace. Record
   only `trace_correlation_outcome=linked` or `unavailable`; never copy trace or
   span IDs, event IDs, OS IDs, payloads, or incident IDs into workflow inputs,
   logs, or shared evidence. A missing link is evidence of unavailable linking,
   not a reason to fabricate one.
7. Wait for the one event to leave the five-minute signal window and confirm the
   incident closes. Allow the 120-second aggregation delay; if it remains open
   through the 30-minute total evidence period, including baseline, stop and
   escalate. Do not create a second event to force resolution.
8. During the signed teardown window, dispatch `disable` with
   `confirm_apply=true`. Verify the owned condition is disabled. Manually detach
   the approved notification route through its separately approved workflow;
   verify it is detached and leave the private dashboard available for review.
9. Still in the signed teardown window, dispatch `evidence` with the UTC start
   and end of the drill, `baseline_failure_count=0`,
   `drill_failure_count=1`, the reviewed trace-link outcome, and every evidence
   confirmation checked. The workflow derives and records the baseline query
   interval as the ten minutes immediately before the drill start. The baseline
   must begin after the signed session starts; the full evidence period,
   including baseline, must be at most 30 minutes and end before the evidence
   run.
   The generated workflow summary is an operator attestation, not a New Relic
   API result; keep direct restricted source evidence in its approved location.

### Done criteria

- The validation, plan, apply, disable, and evidence workflow URLs are recorded
  with the HML session reference.
- The ten-minute baseline interval is recorded with a zero count, and the
  bounded drill query interval is recorded with exactly one failure.
- The private dashboard and single owned condition were verified; an incident
  opened, reached only the approved route, and closed after the event aged out.
- The individual event taxonomy and trace-link outcome were reviewed without
  copying identifiers or customer data into the evidence record.
- The condition is disabled, the notification destination is detached, and no
  incident remains open.
- The sanitized `evidence` summary is present. It contains operator
  attestations, timestamps, counts, and the trace-link outcome only.

If any criterion fails, clean up and report the drill as blocked or failed. Do
not retry the event in the same session or claim live evidence that was not
observed.

## Lifecycle teardown

Use the guarded workflow's `disable` action during the signed teardown window.
It disables only the explicitly owned condition and preserves the dashboard
for review. Detach the drill route manually through its approved workflow and
confirm cleanup before the HML environment is stopped. The provisioner never
attaches or removes notification destinations.
