import json
from copy import deepcopy
from pathlib import Path

import pytest

from scripts.observability.provision_technical_observability import (
    main,
    validate_service_order_definitions,
)

ROOT = Path(__file__).resolve().parents[3]
DASHBOARD_PATH = ROOT / "observability" / "new-relic" / "service-order-dashboard.json"
ALERTS_PATH = ROOT / "observability" / "new-relic" / "service-order-alerts.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_dashboard_covers_volume_durations_and_failures_with_source_metadata():
    dashboard = _load(DASHBOARD_PATH)
    alerts = _load(ALERTS_PATH)

    validate_service_order_definitions(dashboard, alerts)
    widgets = dashboard["pages"][0]["widgets"]
    assert {widget["id"] for widget in widgets} == {
        "service-order-volume-daily",
        "service-order-duration-by-status",
        "service-order-failures-by-type",
    }
    assert all(widget["source"] == "Log" for widget in widgets)
    assert all(widget["time_range"] and widget["unit"] and widget["filters"] for widget in widgets)

    by_id = {widget["id"]: widget for widget in widgets}
    assert "ServiceOrderCreated" in by_id["service-order-volume-daily"]["nrql"]
    duration_query = by_id["service-order-duration-by-status"]["nrql"]
    assert "average(duration_ms)" in duration_query
    assert "Em diagnóstico" in duration_query
    assert "Em execução" in duration_query
    assert "Finalizada" in duration_query
    failure_query = by_id["service-order-failures-by-type"]["nrql"]
    assert "ServiceOrderProcessingFailure" in failure_query
    assert "FACET failure_type, subsystem" in failure_query


def test_failure_alert_has_threshold_route_evaluation_and_runbook():
    alerts = _load(ALERTS_PATH)
    condition = alerts["conditions"][0]

    assert condition["category"] == "service_order_failure"
    assert condition["source"] == "Log"
    assert condition["enabled_during_hml_only"] is True
    assert condition["signal"] == {
        "aggregation_window_seconds": 300,
        "aggregation_method": "EVENT_FLOW",
        "aggregation_delay_seconds": 120,
        "fill_option": "NONE",
    }
    assert condition["terms"] == [
        {
            "priority": "CRITICAL",
            "operator": "ABOVE_OR_EQUALS",
            "threshold": 1,
            "threshold_duration_seconds": 300,
            "threshold_occurrences": "AT_LEAST_ONCE",
        }
    ]
    assert condition["runbook_url"].endswith(
        "new-relic-service-order-dashboard-alerts.md#controlled-hml-drill"
    )
    assert alerts["notification_route"]["logical_name"] == "hml-sre-approved-workflow"
    assert alerts["notification_route"]["attach_by_default"] is False
    assert alerts["notification_route"]["payload_fields"] == [
        "severity",
        "condition_name",
        "service_name",
        "environment",
        "incident_time_utc",
        "runbook_url",
    ]


def test_business_dashboard_and_alert_queries_exclude_personal_and_linking_fields():
    definitions = json.dumps(
        {"dashboard": _load(DASHBOARD_PATH), "alerts": _load(ALERTS_PATH)}
    ).lower()
    forbidden = (
        "select *",
        "service_order_id",
        "event_id",
        "trace.id",
        "span.id",
        "correlation_id",
        "authorization",
        "cookie",
        "request.body",
        "response.body",
        "cpf",
        "cnpj",
        "customer_id",
        "mechanic_name",
    )
    for value in forbidden:
        assert value not in definitions


def test_service_order_validator_rejects_unapproved_query_fields():
    dashboard = _load(DASHBOARD_PATH)
    alerts = _load(ALERTS_PATH)
    unsafe = deepcopy(dashboard)
    unsafe["pages"][0]["widgets"][0]["nrql"] = (
        "FROM Log SELECT count(*) WHERE service_order_id = 17"
    )

    with pytest.raises(ValueError, match="service-order query contract"):
        validate_service_order_definitions(unsafe, alerts)


def test_cli_validates_service_order_profile_and_reports_resource_counts(capsys):
    result = main(
        [
            "validate",
            "--profile",
            "service-order",
            "--dashboard",
            str(DASHBOARD_PATH),
            "--alerts",
            str(ALERTS_PATH),
        ]
    )

    assert result == 0
    result = json.loads(capsys.readouterr().out)
    assert {key: result[key] for key in ("conditions", "status", "widgets")} == {
        "conditions": 1,
        "status": "valid",
        "widgets": 3,
    }


def test_workflow_is_manual_hml_gated_and_requires_business_evidence():
    workflow = (ROOT / ".github" / "workflows" / "new-relic-hml-service-order.yml").read_text(
        encoding="utf-8"
    )

    assert "workflow_dispatch:" in workflow
    assert "github.ref == 'refs/heads/develop'" in workflow
    assert "environment: hml" in workflow
    assert 'validate_environment_window.py --action "$validator_action"' in workflow
    assert "confirm_business_telemetry" in workflow
    assert "confirm_failure_threshold" in workflow
    assert "NEW_RELIC_USER_API_KEY" in workflow
    assert "NEW_RELIC_LICENSE_KEY" not in workflow
    assert "persist-credentials: false" in workflow


def test_runbook_documents_trace_follow_up_privacy_and_controlled_hml_drill():
    runbook = " ".join((
        ROOT / "docs" / "observability" / "new-relic-service-order-dashboard-alerts.md"
    ).read_text(encoding="utf-8").lower().split())

    for value in (
        "daily volume",
        "duration",
        "failure_type",
        "subsystem",
        "trace.id",
        "span.id",
        "hml-sre-approved-workflow",
        "controlled hml drill",
        "lifecycle teardown",
    ):
        assert value in runbook


def test_dashboard_and_condition_link_to_the_manual_single_event_drill():
    dashboard = _load(DASHBOARD_PATH)
    alerts = _load(ALERTS_PATH)

    assert "one-event HML drill is operator-triggered" in dashboard["description"]
    failure_widget = next(
        widget
        for widget in dashboard["pages"][0]["widgets"]
        if widget["id"] == "service-order-failures-by-type"
    )
    assert "approved operator path" in failure_widget["coverage_note"]
    assert alerts["conditions"][0]["runbook_url"].endswith(
        "new-relic-service-order-dashboard-alerts.md#controlled-hml-drill"
    )


def test_drill_workflow_requires_signed_manual_single_event_evidence_and_cleanup():
    workflow = (
        ROOT / ".github" / "workflows" / "new-relic-hml-service-order.yml"
    ).read_text(encoding="utf-8")

    assert "options: [validate, plan, apply, disable, evidence]" in workflow
    assert "session_token:\n        description: Signed coordinator session capability\n        required: true" in workflow
    assert "confirm_notification_route" in workflow
    assert "baseline_failure_count" in workflow
    assert "drill_failure_count" in workflow
    assert "trace_correlation_outcome" in workflow
    for confirmation in (
        "confirm_baseline_clear",
        "confirm_single_failure_observed",
        "confirm_incident_opened",
        "confirm_approved_route_only",
        "confirm_trace_reviewed",
        "confirm_incident_closed",
        "confirm_condition_disabled",
        "confirm_route_detached",
    ):
        assert confirmation in workflow

    assert '[[ "$BASELINE_FAILURE_COUNT" == "0" ]]' in workflow
    assert '[[ "$DRILL_FAILURE_COUNT" == "1" ]]' in workflow
    assert '[[ "$REQUESTED_ACTION" == "disable" || "$REQUESTED_ACTION" == "evidence" ]]' in workflow
    assert "baseline_start = evidence_start - timedelta(minutes=10)" in workflow
    assert "baseline_start < session_start" in workflow
    assert "evidence_end - baseline_start > timedelta(minutes=30)" in workflow
    assert "Baseline query interval (UTC):" in workflow
    assert 'echo "::add-mask::$LIFECYCLE_SESSION_TOKEN"' in workflow
    assert "Operator attestations only" in workflow
    assert "if: inputs.action == 'plan' || inputs.action == 'apply' || inputs.action == 'disable'" in workflow
    assert "confirm_notification_route" in workflow
    assert "curl " not in workflow
    assert "NEW_RELIC_LICENSE_KEY" not in workflow
    assert "NEW_RELIC_NOTIFICATION_DESTINATION_ID" not in workflow


def test_drill_runbook_defines_bounded_query_evidence_sequence_and_done_criteria():
    runbook = " ".join((
        ROOT / "docs" / "observability" / "new-relic-service-order-dashboard-alerts.md"
    ).read_text(encoding="utf-8").lower().split())

    for value in (
        "## controlled hml drill",
        "baseline_failure_count",
        "drill_failure_count",
        "sinCE <drill_start_epoch_ms> until <drill_end_epoch_ms>",
        "exactly one synthetic `serviceorderprocessingfailure`",
        "condition should open an incident",
        "incident closes",
        "manually attach",
        "manually detach",
        "trace_correlation_outcome",
        "operator attestation",
        "done criteria",
        "stop and record the drill as blocked",
    ):
        assert value.lower() in runbook


def test_event_contract_keeps_drill_correlation_out_of_saved_evidence():
    event_contract = " ".join((
        ROOT / "docs" / "observability" / "new-relic-service-order-events.md"
    ).read_text(encoding="utf-8").lower().split())

    assert "single synthetic failure" in event_contract
    assert "trace.id" in event_contract
    assert "span.id" in event_contract
    assert "do not copy raw trace identifiers into the workflow evidence" in event_contract
    assert "customer data" in event_contract
