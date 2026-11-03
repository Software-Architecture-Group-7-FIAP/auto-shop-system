"""Validate and reconcile the owned New Relic HML technical dashboard and alerts."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from collections.abc import Mapping
from pathlib import Path

if __package__:
    from .nerdgraph_client import (
        CONDITION_CREATE,
        CONDITION_SEARCH,
        CONDITION_UPDATE,
        DASHBOARD_CREATE,
        DASHBOARD_GET,
        DASHBOARD_SEARCH,
        DASHBOARD_UPDATE,
        ENDPOINTS,
        POLICY_CREATE,
        POLICY_SEARCH,
        POLICY_UPDATE,
        TAG_ENTITY,
        NerdGraphClient,
        ProvisioningError,
    )
else:
    from nerdgraph_client import (
        CONDITION_CREATE,
        CONDITION_SEARCH,
        CONDITION_UPDATE,
        DASHBOARD_CREATE,
        DASHBOARD_GET,
        DASHBOARD_SEARCH,
        DASHBOARD_UPDATE,
        ENDPOINTS,
        POLICY_CREATE,
        POLICY_SEARCH,
        POLICY_UPDATE,
        TAG_ENTITY,
        NerdGraphClient,
        ProvisioningError,
    )


OWNERSHIP_PATTERN = re.compile(r"^auto-shop-owned-[a-z0-9-]{1,64}$")
RESOURCE_NAME_PATTERN = re.compile(r"^auto-shop-owned::[A-Za-z0-9 .:_/-]{1,96}$")
SAFE_ID_PATTERN = re.compile(r"^[a-z0-9-]{1,64}$")
RUNBOOK_PREFIX = (
    "https://github.com/Software-Architecture-Group-7-FIAP/"
    "auto-shop-system/blob/develop/docs/observability/"
)
FORBIDDEN_QUERY_TERMS = (
    "select *",
    " from log ",
    "latest(message)",
    "correlation_id",
    "trace.id",
    "span.id",
    "service_order_id",
    "authorization",
    "cookie",
    "request.body",
    "response.body",
    "customer_id",
    "mechanic_name",
    "cpf",
    "cnpj",
    "email",
)

SERVICE_ORDER_OWNERSHIP = "auto-shop-owned-hml-service-order-v2"
SERVICE_ORDER_DASHBOARD_NAME = "auto-shop-owned::HML Service Order Operations v2"
SERVICE_ORDER_POLICY_NAME = "auto-shop-owned::HML Service Order Failures"
SOURCE_COVERAGE_STATUS = {
    "Transaction": "verified",
    "ApiGatewaySample": "excluded",
    "ServerlessSample": "gated",
    "K8sPodSample": "verified",
    "K8sContainerSample": "verified",
    "K8sHpaSample": "verified",
}
TECHNICAL_WIDGET_SOURCES = {
    "fastapi-throughput": "Transaction",
    "fastapi-availability-errors": "Transaction",
    "fastapi-latency": "Transaction",
    "gateway-volume-errors": "ApiGatewaySample",
    "gateway-error-availability": "ApiGatewaySample",
    "gateway-latency": "ApiGatewaySample",
    "lambda-auth-health": "ServerlessSample",
    "k8s-pod-resources": "K8sPodSample",
    "k8s-readiness": "K8sPodSample",
    "k8s-restarts": "K8sContainerSample",
    "k8s-hpa": "K8sHpaSample",
}
TECHNICAL_ALERT_CONTRACTS = {
    "api-availability": ("api_availability", "Transaction"),
    "api-latency": ("api_latency", "Transaction"),
    "api-error-rate": ("api_error_rate", "Transaction"),
    "k8s-readiness": ("k8s_readiness", "K8sPodSample"),
    "k8s-restarts": ("k8s_restarts", "K8sContainerSample"),
    "k8s-cpu": ("k8s_cpu", "K8sPodSample"),
    "k8s-memory": ("k8s_memory", "K8sPodSample"),
}
SOURCE_REQUIRED_HML_SCOPE = {
    "Transaction": ("appname = 'auto-shop-api'", "label.environment = 'hml'"),
    "ApiGatewaySample": ("stage = 'hml'",),
    "ServerlessSample": ("provider.functionname = 'lambda-auth-hml'",),
    "K8sPodSample": (
        "clustername = 'auto-shop-hml'",
        "namespacename = 'auto-shop-hml'",
    ),
    "K8sContainerSample": (
        "clustername = 'auto-shop-hml'",
        "namespacename = 'auto-shop-hml'",
    ),
    "K8sHpaSample": (
        "clustername = 'auto-shop-hml'",
        "namespacename = 'auto-shop-hml'",
    ),
}
SERVICE_ORDER_WIDGET_CONTRACTS = {
    "service-order-volume-daily": {
        "title": "Daily service-order volume (orders/day)",
        "time_range": "7 days",
        "unit": "orders/day",
        "filters": [
            "event = ServiceOrderCreated",
            "event_version = 1",
            "service = auto-shop-api",
            "environment = staging",
        ],
        "nrql": (
            "FROM Log SELECT count(*) WHERE event = 'ServiceOrderCreated' "
            "AND event_version = 1 AND service = 'auto-shop-api' "
            "AND environment = 'staging' SINCE 7 days ago TIMESERIES 1 day"
        ),
    },
    "service-order-duration-by-status": {
        "title": "Average completed status duration (minutes)",
        "time_range": "7 days",
        "unit": "minutes",
        "filters": [
            "event = ServiceOrderStatusDuration",
            "event_version = 1",
            "status IN diagnosis, execution, finalization",
            "service = auto-shop-api",
            "environment = staging",
        ],
        "nrql": (
            "FROM Log SELECT average(duration_ms) / 60000 AS 'average minutes' "
            "WHERE event = 'ServiceOrderStatusDuration' AND event_version = 1 "
            "AND status IN ('Em diagnóstico', 'Em execução', 'Finalizada') "
            "AND service = 'auto-shop-api' AND environment = 'staging' "
            "SINCE 7 days ago TIMESERIES 1 day FACET status"
        ),
    },
    "service-order-failures-by-type": {
        "title": "Service-order processing failures by type and subsystem",
        "time_range": "24 hours",
        "unit": "failures/hour",
        "filters": [
            "event = ServiceOrderProcessingFailure",
            "event_version = 1",
            "service = auto-shop-api",
            "environment = staging",
        ],
        "nrql": (
            "FROM Log SELECT count(*) WHERE event = 'ServiceOrderProcessingFailure' "
            "AND event_version = 1 AND service = 'auto-shop-api' "
            "AND environment = 'staging' SINCE 24 hours ago "
            "TIMESERIES 1 hour FACET failure_type, subsystem"
        ),
    },
}
SERVICE_ORDER_ALERT_QUERY = (
    "FROM Log SELECT count(*) WHERE event = 'ServiceOrderProcessingFailure' "
    "AND event_version = 1 AND service = 'auto-shop-api' AND environment = 'staging'"
)

def _require_exact_keys(value: dict, allowed: set[str], context: str) -> None:
    unknown = set(value) - allowed
    if unknown:
        raise ValueError(f"{context} contains unknown fields")


def _validate_query(query: object, *, bounded: bool, expected_source: str) -> str:
    if not isinstance(query, str) or not 20 <= len(query) <= 2_000:
        raise ValueError("NRQL query length is invalid")
    lowered = f" {' '.join(query.lower().split())} "
    normalized_forbidden = tuple(" ".join(term.lower().split()) for term in FORBIDDEN_QUERY_TERMS)
    if any(term in lowered for term in normalized_forbidden):
        raise ValueError("NRQL query violates the aggregate privacy contract")
    if bounded and " since 30 minutes ago" not in lowered:
        raise ValueError("Dashboard NRQL must use the fixed 30-minute range")
    if "select" not in lowered or "from" not in lowered or "where" not in lowered:
        raise ValueError("NRQL query must be aggregate and filtered")
    if not re.search(rf"\bfrom\s+{re.escape(expected_source.lower())}\b", lowered):
        raise ValueError("NRQL source does not match its declared source")
    if not any(
        token in lowered
        for token in (
            "count(",
            "rate(",
            "percentage(",
            "percentile(",
            "sum(",
            "average(",
            "latest(",
            "max(",
            "uniquecount(",
            "filter(",
        )
    ):
        raise ValueError("NRQL query must use an approved aggregate")
    return query


def _source_is_verified(source: object, coverage_status: object, context: str) -> bool:
    expected_status = SOURCE_COVERAGE_STATUS.get(source) if isinstance(source, str) else None
    if expected_status is None or coverage_status != expected_status:
        raise ValueError(f"{context} coverage status does not match the reviewed source policy")
    return expected_status == "verified"


def _validate_hml_source_scope(query: str, source: str) -> None:
    normalized = f" {' '.join(query.lower().split())} "
    required_scope = SOURCE_REQUIRED_HML_SCOPE.get(source)
    if required_scope is None or " where " not in normalized:
        raise ValueError("NRQL query does not match the required HML scope for its source")
    filter_clause = normalized.rsplit(" where ", 1)[1]
    filter_clause = re.split(
        r"\b(?:facet|timeseries|since|limit|order by)\b",
        filter_clause,
        maxsplit=1,
    )[0].strip()
    required_prefix = " and ".join(required_scope)
    if (
        re.search(r"\bor\b", filter_clause)
        or not filter_clause.startswith(required_prefix)
        or (
            len(filter_clause) > len(required_prefix)
            and not filter_clause[len(required_prefix) :].startswith(" and ")
        )
    ):
        raise ValueError("NRQL query does not match the required HML scope for its source")


def _verified_dashboard_subset(dashboard: dict) -> tuple[dict, int, int]:
    total_widgets = 0
    eligible_widgets = 0
    pages = []
    for page in dashboard["pages"]:
        widgets = []
        for widget in page["widgets"]:
            total_widgets += 1
            if _source_is_verified(
                widget.get("source"),
                widget.get("coverage_status"),
                "Dashboard widget",
            ):
                widgets.append(widget)
                eligible_widgets += 1
        if widgets:
            pages.append({**page, "widgets": widgets})
    if not eligible_widgets:
        raise ValueError("No verified dashboard widgets are eligible for reconciliation")
    return {**dashboard, "pages": pages}, total_widgets, eligible_widgets


def _verified_alerts_subset(alerts: dict) -> tuple[dict, int, int]:
    total_conditions = 0
    eligible_conditions = 0
    conditions = []
    for condition in alerts["conditions"]:
        total_conditions += 1
        if _source_is_verified(
            condition.get("source"),
            condition.get("coverage_status"),
            "Alert condition",
        ):
            conditions.append(condition)
            eligible_conditions += 1
    if not eligible_conditions:
        raise ValueError("No verified alert conditions are eligible for reconciliation")
    return {**alerts, "conditions": conditions}, total_conditions, eligible_conditions


def validate_definitions(
    dashboard: dict,
    alerts: dict,
) -> None:
    _require_exact_keys(
        dashboard,
        {
            "schema_version",
            "ownership",
            "name",
            "description",
            "permissions",
            "pages",
        },
        "dashboard",
    )
    if dashboard.get("schema_version") != 1:
        raise ValueError("Unsupported dashboard schema version")
    if not OWNERSHIP_PATTERN.fullmatch(str(dashboard.get("ownership", ""))):
        raise ValueError("Invalid ownership marker")
    if not RESOURCE_NAME_PATTERN.fullmatch(str(dashboard.get("name", ""))):
        raise ValueError("Invalid dashboard name")
    pages = dashboard.get("pages")
    if not isinstance(pages, list) or len(pages) != 2:
        raise ValueError("Dashboard must contain exactly two pages")
    page_names: set[str] = set()
    widget_ids: set[str] = set()
    widget_count = 0
    for page in pages:
        _require_exact_keys(page, {"name", "widgets"}, "dashboard page")
        page_name = page.get("name")
        if (
            not isinstance(page_name, str)
            or not 1 <= len(page_name) <= 120
            or page_name in page_names
        ):
            raise ValueError("Invalid or duplicate dashboard page name")
        page_names.add(page_name)
        if not isinstance(page.get("widgets"), list):
            raise TypeError("Dashboard page widgets must be a list")
        page_widget_titles: set[str] = set()
        for widget in page["widgets"]:
            _require_exact_keys(
                widget,
                {
                    "id",
                    "title",
                    "visualization",
                    "source",
                    "time_range",
                    "unit",
                    "filters",
                    "coverage_note",
                    "coverage_status",
                    "nrql",
                },
                "dashboard widget",
            )
            widget_id = widget.get("id")
            if not isinstance(widget_id, str) or not SAFE_ID_PATTERN.fullmatch(widget_id):
                raise ValueError("Invalid dashboard widget ID")
            expected_source = TECHNICAL_WIDGET_SOURCES.get(widget_id)
            if expected_source is None:
                raise ValueError("Unreviewed dashboard widget ID")
            if widget_id in widget_ids:
                raise ValueError("Duplicate dashboard widget ID")
            widget_ids.add(widget_id)
            title = widget.get("title")
            if not isinstance(title, str) or title in page_widget_titles:
                raise ValueError("Invalid or duplicate dashboard widget title")
            page_widget_titles.add(title)
            if widget.get("visualization") not in {"line", "billboard"}:
                raise ValueError("Invalid dashboard visualization")
            if widget.get("time_range") != "30 minutes":
                raise ValueError("Invalid dashboard time range")
            if not isinstance(widget.get("filters"), list) or not widget["filters"]:
                raise ValueError("Dashboard widget filters are required")
            source = widget.get("source")
            if source not in SOURCE_COVERAGE_STATUS:
                raise ValueError("Invalid dashboard source")
            if source != expected_source:
                raise ValueError("Dashboard widget source does not match its reviewed source contract")
            coverage_status = widget.get("coverage_status")
            if not _source_is_verified(source, coverage_status, "Dashboard widget"):
                coverage_note = widget.get("coverage_note")
                if not isinstance(coverage_note, str) or not coverage_note.strip():
                    raise ValueError("Gated dashboard widgets require an explicit coverage note")
            for field_name in ("title", "unit"):
                field_value = widget.get(field_name)
                if not isinstance(field_value, str) or not 1 <= len(field_value) <= 120:
                    raise ValueError("Invalid dashboard display field")
            query = _validate_query(widget.get("nrql"), bounded=True, expected_source=source)
            _validate_hml_source_scope(query, source)
            widget_count += 1
    if widget_count != 11 or widget_ids != set(TECHNICAL_WIDGET_SOURCES):
        raise ValueError("Dashboard must contain exactly eleven widgets")

    _require_exact_keys(
        alerts,
        {"schema_version", "ownership", "policy", "notification_route", "conditions"},
        "alerts",
    )
    if alerts.get("schema_version") != 1 or alerts.get("ownership") != dashboard["ownership"]:
        raise ValueError("Dashboard and alert ownership must match")
    policy = alerts.get("policy")
    if not isinstance(policy, dict) or set(policy) != {"name", "incident_preference"}:
        raise ValueError("Invalid alert policy contract")
    if not RESOURCE_NAME_PATTERN.fullmatch(str(policy.get("name", ""))):
        raise ValueError("Invalid owned alert policy name")
    if policy.get("incident_preference") != "PER_CONDITION_AND_TARGET":
        raise ValueError("Invalid alert incident preference")
    route = alerts.get("notification_route")
    if not isinstance(route, dict) or set(route) != {
        "logical_name",
        "attach_by_default",
        "owner",
        "runtime_secret",
    }:
        raise ValueError("Invalid notification route contract")
    if route.get("attach_by_default") is not False:
        raise ValueError("Notification route attachment must be separately confirmed")
    conditions = alerts.get("conditions")
    if not isinstance(conditions, list) or len(conditions) != 7:
        raise ValueError("Exactly seven alert conditions are required")
    condition_ids: set[str] = set()
    condition_names: set[str] = set()
    for condition in conditions:
        _require_exact_keys(
            condition,
            {
                "id",
                "name",
                "category",
                "source",
                "nrql",
                "signal",
                "terms",
                "coverage_status",
                "coverage_note",
                "loss_of_signal",
                "enabled_during_hml_only",
                "runbook_url",
            },
            "alert condition",
        )
        condition_id = condition.get("id")
        if not isinstance(condition_id, str) or not SAFE_ID_PATTERN.fullmatch(condition_id):
            raise ValueError("Invalid alert condition ID")
        expected_contract = TECHNICAL_ALERT_CONTRACTS.get(condition_id)
        if expected_contract is None:
            raise ValueError("Unreviewed alert condition ID")
        if condition_id in condition_ids:
            raise ValueError("Duplicate alert condition ID")
        condition_ids.add(condition_id)
        condition_name = condition.get("name")
        if not RESOURCE_NAME_PATTERN.fullmatch(str(condition_name or "")):
            raise ValueError("Invalid owned alert condition name")
        if condition_name in condition_names:
            raise ValueError("Duplicate alert condition name")
        condition_names.add(condition_name)
        source = condition.get("source")
        if source not in SOURCE_COVERAGE_STATUS:
            raise ValueError("Invalid alert source")
        if (condition.get("category"), source) != expected_contract:
            raise ValueError("Alert condition source does not match its reviewed source contract")
        if not _source_is_verified(
            source,
            condition.get("coverage_status"),
            "Alert condition",
        ):
            coverage_note = condition.get("coverage_note")
            if not isinstance(coverage_note, str) or not coverage_note.strip():
                raise ValueError("Gated alert conditions require an explicit coverage note")
        query = _validate_query(condition.get("nrql"), bounded=False, expected_source=source)
        _validate_hml_source_scope(query, source)
        if condition.get("enabled_during_hml_only") is not True:
            raise ValueError("Alert condition must be scoped to the HML lifecycle")
        if condition.get("loss_of_signal") != {"enabled": False}:
            raise ValueError("Ephemeral HML alerts must not page on loss of signal")
        if not str(condition.get("runbook_url", "")).startswith(RUNBOOK_PREFIX):
            raise ValueError("Alert runbook URL is not approved")
        signal = condition.get("signal")
        if not isinstance(signal, dict) or set(signal) != {
            "aggregation_window_seconds",
            "aggregation_method",
            "aggregation_delay_seconds",
            "fill_option",
        }:
            raise ValueError("Invalid alert signal contract")
        if signal["aggregation_window_seconds"] not in {60, 300}:
            raise ValueError("Invalid alert aggregation window")
        if signal["aggregation_method"] != "EVENT_FLOW":
            raise ValueError("Invalid alert aggregation method")
        if signal["fill_option"] != "NONE":
            raise ValueError("Invalid alert fill option")
        if signal["aggregation_delay_seconds"] not in {60, 120, 180}:
            raise ValueError("Invalid alert aggregation delay")
        terms = condition.get("terms")
        if not isinstance(terms, list) or not 1 <= len(terms) <= 2:
            raise ValueError("Invalid alert terms")
        for term in terms:
            if term.get("priority") not in {"WARNING", "CRITICAL"}:
                raise ValueError("Invalid alert severity")
            if term.get("operator") not in {"ABOVE", "ABOVE_OR_EQUALS", "BELOW"}:
                raise ValueError("Invalid alert operator")
            threshold = term.get("threshold")
            if (
                isinstance(threshold, bool)
                or not isinstance(threshold, (int, float))
                or not math.isfinite(threshold)
                or threshold <= 0
                or threshold > 1_000_000_000
            ):
                raise ValueError("Invalid alert threshold")
            if term.get("threshold_occurrences") not in {"ALL", "AT_LEAST_ONCE"}:
                raise ValueError("Invalid alert threshold occurrences")
            if not 0 < term.get("threshold_duration_seconds", 0) <= 3_600:
                raise ValueError("Invalid alert evaluation duration")
    if condition_ids != set(TECHNICAL_ALERT_CONTRACTS):
        raise ValueError("Exactly seven reviewed alert conditions are required")


def validate_service_order_definitions(dashboard: dict, alerts: dict) -> None:
    _require_exact_keys(
        dashboard,
        {"schema_version", "ownership", "name", "description", "permissions", "pages"},
        "service-order dashboard",
    )
    if dashboard.get("schema_version") != 1:
        raise ValueError("Unsupported service-order dashboard schema version")
    if dashboard.get("ownership") != SERVICE_ORDER_OWNERSHIP:
        raise ValueError("Invalid service-order dashboard ownership")
    if dashboard.get("name") != SERVICE_ORDER_DASHBOARD_NAME:
        raise ValueError("Invalid service-order dashboard name")
    if dashboard.get("permissions") != "PRIVATE":
        raise ValueError("Service-order dashboard must remain private")
    description = dashboard.get("description")
    if not isinstance(description, str) or not 1 <= len(description) <= 500:
        raise ValueError("Invalid service-order dashboard description")
    pages = dashboard.get("pages")
    if not isinstance(pages, list) or len(pages) != 1:
        raise ValueError("Service-order dashboard must contain one page")
    page = pages[0]
    _require_exact_keys(page, {"name", "widgets"}, "service-order dashboard page")
    if page.get("name") != "Service Orders":
        raise ValueError("Invalid service-order dashboard page")
    widgets = page.get("widgets")
    if not isinstance(widgets, list) or len(widgets) != len(SERVICE_ORDER_WIDGET_CONTRACTS):
        raise ValueError("Service-order dashboard widget count is invalid")
    widget_ids: set[str] = set()
    for widget in widgets:
        _require_exact_keys(
            widget,
            {
                "id",
                "title",
                "visualization",
                "source",
                "time_range",
                "unit",
                "filters",
                "coverage_note",
                "nrql",
            },
            "service-order dashboard widget",
        )
        widget_id = widget.get("id")
        if widget_id not in SERVICE_ORDER_WIDGET_CONTRACTS or widget_id in widget_ids:
            raise ValueError("Invalid service-order dashboard widget ID")
        widget_ids.add(widget_id)
        contract = SERVICE_ORDER_WIDGET_CONTRACTS[widget_id]
        if (
            widget.get("title") != contract["title"]
            or widget.get("source") != "Log"
            or widget.get("time_range") != contract["time_range"]
            or widget.get("unit") != contract["unit"]
            or widget.get("filters") != contract["filters"]
            or widget.get("nrql") != contract["nrql"]
        ):
            raise ValueError("Invalid service-order query contract")
        if widget.get("visualization") not in {"line", "billboard"}:
            raise ValueError("Invalid service-order dashboard visualization")
        coverage_note = widget.get("coverage_note")
        if not isinstance(coverage_note, str) or not 1 <= len(coverage_note) <= 500:
            raise ValueError("Invalid service-order dashboard coverage note")
    if widget_ids != set(SERVICE_ORDER_WIDGET_CONTRACTS):
        raise ValueError("Service-order dashboard is missing a required widget")

    _require_exact_keys(
        alerts,
        {"schema_version", "ownership", "policy", "notification_route", "conditions"},
        "service-order alerts",
    )
    if alerts.get("schema_version") != 1 or alerts.get("ownership") != SERVICE_ORDER_OWNERSHIP:
        raise ValueError("Service-order dashboard and alert ownership must match")
    policy = alerts.get("policy")
    if not isinstance(policy, dict) or policy != {
        "name": SERVICE_ORDER_POLICY_NAME,
        "incident_preference": "PER_CONDITION_AND_TARGET",
    }:
        raise ValueError("Invalid service-order alert policy")
    route = alerts.get("notification_route")
    if not isinstance(route, dict) or route != {
        "logical_name": "hml-sre-approved-workflow",
        "attach_by_default": False,
        "owner": "HML SRE on-call",
        "runtime_secret": "NEW_RELIC_NOTIFICATION_DESTINATION_ID",
        "payload_fields": [
            "severity",
            "condition_name",
            "service_name",
            "environment",
            "incident_time_utc",
            "runbook_url",
        ],
    }:
        raise ValueError("Invalid service-order notification route")
    conditions = alerts.get("conditions")
    if not isinstance(conditions, list) or len(conditions) != 1:
        raise ValueError("Exactly one service-order alert condition is required")
    condition = conditions[0]
    _require_exact_keys(
        condition,
        {
            "id",
            "name",
            "category",
            "source",
            "nrql",
            "signal",
            "terms",
            "loss_of_signal",
            "enabled_during_hml_only",
            "runbook_url",
        },
        "service-order alert condition",
    )
    if (
        condition.get("id") != "service-order-failure"
        or condition.get("name") != "auto-shop-owned::HML Service-order processing failure"
        or condition.get("category") != "service_order_failure"
        or condition.get("source") != "Log"
        or condition.get("nrql") != SERVICE_ORDER_ALERT_QUERY
    ):
        raise ValueError("Invalid service-order failure alert contract")
    if condition.get("enabled_during_hml_only") is not True:
        raise ValueError("Service-order alert must be scoped to the HML lifecycle")
    if condition.get("loss_of_signal") != {"enabled": False}:
        raise ValueError("Service-order alerts must not page on HML loss of signal")
    runbook_url = condition.get("runbook_url")
    if not isinstance(runbook_url, str) or not runbook_url.startswith(RUNBOOK_PREFIX):
        raise ValueError("Service-order alert runbook URL is not approved")
    signal = condition.get("signal")
    if signal != {
        "aggregation_window_seconds": 300,
        "aggregation_method": "EVENT_FLOW",
        "aggregation_delay_seconds": 120,
        "fill_option": "NONE",
    }:
        raise ValueError("Invalid service-order alert evaluation window")
    if condition.get("terms") != [
        {
            "priority": "CRITICAL",
            "operator": "ABOVE_OR_EQUALS",
            "threshold": 1,
            "threshold_duration_seconds": 300,
            "threshold_occurrences": "AT_LEAST_ONCE",
        }
    ]:
        raise ValueError("Invalid service-order failure threshold")

    serialized = json.dumps({"dashboard": dashboard, "alerts": alerts}).lower()
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
    if any(term in serialized for term in forbidden):
        raise ValueError("Service-order dashboard violates the telemetry privacy contract")


def _load_json(path: Path) -> dict:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            parse_constant=lambda _value: (_ for _ in ()).throw(
                ValueError("Non-finite JSON numbers are not allowed")
            ),
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError("Could not load an observability definition") from None
    if not isinstance(value, dict):
        raise TypeError("Observability definition must be a JSON object")
    return value


def _dashboard_input(
    definition: dict,
    account_id: int,
    existing: dict[str, object] | None = None,
) -> dict[str, object]:
    existing_pages = {
        page.get("name"): page
        for page in (existing or {}).get("pages", [])
        if isinstance(page, dict)
    }
    pages = []
    for page in definition["pages"]:
        existing_page = existing_pages.get(page["name"], {})
        existing_widgets = {
            widget.get("title"): widget
            for widget in existing_page.get("widgets", [])
            if isinstance(widget, dict)
        }
        widgets = []
        for index, widget in enumerate(page["widgets"]):
            widget_input = {
                "title": widget["title"],
                "visualization": {"id": f"viz.{widget['visualization']}"},
                "layout": {
                    "row": (index // 2) * 3 + 1,
                    "column": 1 if index % 2 == 0 else 7,
                    "width": 6,
                    "height": 3,
                },
                "rawConfiguration": {
                    "nrqlQueries": [
                        {"accountIds": [account_id], "query": widget["nrql"]}
                    ]
                },
            }
            existing_widget = existing_widgets.get(widget["title"])
            if existing_widget and existing_widget.get("id"):
                widget_input["id"] = existing_widget["id"]
            widgets.append(widget_input)
        page_input = {"name": page["name"], "widgets": widgets}
        if existing_page.get("guid"):
            page_input["guid"] = existing_page["guid"]
        pages.append(page_input)
    return {
        "name": definition["name"],
        "description": definition["description"],
        "permissions": definition["permissions"],
        "pages": pages,
    }


def _condition_input(condition: dict, *, enabled: bool) -> dict[str, object]:
    signal = condition["signal"]
    return {
        "name": condition["name"],
        "description": f"Owned aggregate HML condition: {condition['category']}",
        "enabled": enabled,
        "nrql": {"query": condition["nrql"]},
        "runbookUrl": condition["runbook_url"],
        "valueFunction": "SINGLE_VALUE",
        "signal": {
            "aggregationWindow": signal["aggregation_window_seconds"],
            "aggregationMethod": signal["aggregation_method"],
            "aggregationDelay": signal["aggregation_delay_seconds"],
            "fillOption": signal["fill_option"],
        },
        "terms": [
            {
                "priority": term["priority"],
                "operator": term["operator"],
                "threshold": term["threshold"],
                "thresholdDuration": term["threshold_duration_seconds"],
                "thresholdOccurrences": term["threshold_occurrences"],
            }
            for term in condition["terms"]
        ],
        "violationTimeLimitSeconds": 86_400,
    }


def _positive_account_id(raw: str) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise ValueError("NEW_RELIC_ACCOUNT_ID must be a positive integer") from None
    if not 1 <= value <= 2_147_483_647:
        raise ValueError("NEW_RELIC_ACCOUNT_ID must be a positive integer")
    return value


def _entities(data: dict) -> list[dict]:
    try:
        values = data["actor"]["entitySearch"]["results"]["entities"]
    except (KeyError, TypeError):
        raise ProvisioningError("NerdGraph dashboard discovery response was invalid") from None
    if not isinstance(values, list) or any(not isinstance(value, dict) for value in values):
        raise ProvisioningError("NerdGraph dashboard discovery response was invalid")
    return values


def _has_ownership_tag(entity: dict, ownership: str) -> bool:
    tags = entity.get("tags")
    if not isinstance(tags, list):
        return False
    return any(
        tag.get("key") == "auto-shop.ownership"
        and isinstance(tag.get("values"), list)
        and ownership in tag["values"]
        for tag in tags
        if isinstance(tag, dict)
    )


def _dashboard_structure(data: dict, account_id: int) -> dict[str, object]:
    try:
        entity = data["actor"]["entity"]
    except (KeyError, TypeError):
        raise ProvisioningError("NerdGraph dashboard structure response was invalid") from None
    if not isinstance(entity, dict) or entity.get("accountId") != account_id:
        raise ProvisioningError("Owned dashboard account verification failed")
    if not isinstance(entity.get("pages"), list):
        raise ProvisioningError("NerdGraph dashboard structure response was invalid")
    return entity


def _dashboard_mutation_guid(data: dict, field: str) -> str:
    try:
        result = data[field]
        errors = result["errors"]
        guid = result["entityResult"]["guid"]
    except (KeyError, TypeError):
        raise ProvisioningError("NerdGraph dashboard mutation response was invalid") from None
    if errors:
        raise ProvisioningError("NerdGraph dashboard mutation was rejected")
    if not isinstance(guid, str) or not guid:
        raise ProvisioningError("NerdGraph dashboard mutation response was invalid")
    return guid


def _tag_owned_dashboard(
    client: NerdGraphClient,
    guid: str,
    ownership: str,
) -> None:
    data = client.execute(
        TAG_ENTITY,
        {
            "guid": guid,
            "tags": [{"key": "auto-shop.ownership", "values": [ownership]}],
        },
    )
    try:
        errors = data["taggingAddTagsToEntity"]["errors"]
    except (KeyError, TypeError):
        raise ProvisioningError("NerdGraph ownership tagging response was invalid") from None
    if errors:
        raise ProvisioningError("NerdGraph ownership tagging was rejected")


def reconcile(
    client: NerdGraphClient,
    account_id: int,
    dashboard: dict,
    alerts: dict,
    *,
    action: str,
    profile: str = "technical",
) -> dict[str, object]:
    if action not in {"plan", "apply", "disable"}:
        raise ValueError("Unsupported reconciliation action")
    if profile not in {"technical", "service-order"}:
        raise ValueError("Unsupported reconciliation profile")
    if profile == "technical":
        validate_definitions(dashboard, alerts)
        dashboard, total_widgets, eligible_widgets = _verified_dashboard_subset(dashboard)
        alerts, total_conditions, eligible_conditions = _verified_alerts_subset(alerts)
    else:
        total_widgets = sum(len(page["widgets"]) for page in dashboard["pages"])
        eligible_widgets = total_widgets
        total_conditions = len(alerts["conditions"])
        eligible_conditions = total_conditions
    coverage_summary = {
        "eligible_widgets": eligible_widgets,
        "excluded_widgets": total_widgets - eligible_widgets,
        "eligible_conditions": eligible_conditions,
        "excluded_conditions": total_conditions - eligible_conditions,
    }
    entity_query = (
        f"accountId = {account_id} AND type = 'DASHBOARD' "
        f"AND name = '{dashboard['name']}'"
    )
    dashboards = [
        item
        for item in _entities(client.execute(DASHBOARD_SEARCH, {"query": entity_query}))
        if item.get("name") == dashboard["name"]
        and item.get("type") == "DASHBOARD"
        and item.get("accountId") == account_id
    ]
    if len(dashboards) > 1:
        raise ProvisioningError("Owned dashboard discovery was ambiguous")
    if dashboards and not _has_ownership_tag(dashboards[0], dashboard["ownership"]):
        raise ProvisioningError("Same-named dashboard is not owned by this repository")
    if action == "apply":
        if dashboards:
            existing = _dashboard_structure(
                client.execute(DASHBOARD_GET, {"guid": dashboards[0]["guid"]}),
                account_id,
            )
            dashboard_input = _dashboard_input(dashboard, account_id, existing)
            mutation = client.execute(
                DASHBOARD_UPDATE,
                {"guid": dashboards[0]["guid"], "dashboard": dashboard_input},
            )
            dashboard_guid = _dashboard_mutation_guid(mutation, "dashboardUpdate")
        else:
            dashboard_input = _dashboard_input(dashboard, account_id)
            mutation = client.execute(
                DASHBOARD_CREATE,
                {"accountId": account_id, "dashboard": dashboard_input},
            )
            dashboard_guid = _dashboard_mutation_guid(mutation, "dashboardCreate")
        _tag_owned_dashboard(client, dashboard_guid, dashboard["ownership"])

    policy_data = client.execute(
        POLICY_SEARCH,
        {"accountId": account_id, "name": alerts["policy"]["name"]},
    )
    try:
        policies = policy_data["actor"]["account"]["alerts"]["policiesSearch"]["policies"]
    except (KeyError, TypeError):
        raise ProvisioningError("NerdGraph alert policy discovery response was invalid") from None
    policies = [item for item in policies if item.get("name") == alerts["policy"]["name"]]
    if len(policies) > 1:
        raise ProvisioningError("Owned alert policy discovery was ambiguous")
    if action == "plan":
        if not policies:
            return {
                **coverage_summary,
                "dashboard": "update" if dashboards else "create",
                "policy": "create",
                "conditions_create": len(alerts["conditions"]),
                "conditions_update": 0,
                "notifications": "not-attached",
            }
        condition_data = client.execute(
            CONDITION_SEARCH,
            {"accountId": account_id, "policyId": policies[0]["id"]},
        )
        try:
            existing = condition_data["actor"]["account"]["alerts"]["nrqlConditionsSearch"]["nrqlConditions"]
        except (KeyError, TypeError):
            raise ProvisioningError("NerdGraph alert condition discovery response was invalid") from None
        owned_names = {
            item["name"]
            for item in existing
            if item.get("name", "").startswith("auto-shop-owned::")
        }
        expected_names = {condition["name"] for condition in alerts["conditions"]}
        stale_names = owned_names - expected_names
        if stale_names:
            raise ProvisioningError("Unexpected owned alert conditions require manual review")
        return {
            **coverage_summary,
            "dashboard": "update" if dashboards else "create",
            "policy": "update",
            "conditions_create": len(expected_names - owned_names),
            "conditions_update": len(expected_names & owned_names),
            "notifications": "not-attached",
        }
    if not policies:
        if action == "disable":
            return {
                **coverage_summary,
                "dashboard": "unchanged",
                "policy": "absent",
                "conditions": 0,
            }
        created = client.execute(
            POLICY_CREATE,
            {
                "accountId": account_id,
                "policy": {
                    "name": alerts["policy"]["name"],
                    "incidentPreference": alerts["policy"]["incident_preference"],
                },
            },
        )
        try:
            policy_id = created["alertsPolicyCreate"]["id"]
        except (KeyError, TypeError):
            raise ProvisioningError("NerdGraph alert policy creation response was invalid") from None
    else:
        policy_id = policies[0]["id"]
        if action == "apply":
            client.execute(
                POLICY_UPDATE,
                {
                    "accountId": account_id,
                    "policyId": policy_id,
                    "policy": {
                        "name": alerts["policy"]["name"],
                        "incidentPreference": alerts["policy"]["incident_preference"],
                    },
                },
            )
    condition_data = client.execute(
        CONDITION_SEARCH,
        {"accountId": account_id, "policyId": policy_id},
    )
    try:
        existing = condition_data["actor"]["account"]["alerts"]["nrqlConditionsSearch"]["nrqlConditions"]
    except (KeyError, TypeError):
        raise ProvisioningError("NerdGraph alert condition discovery response was invalid") from None
    owned = [
        item
        for item in existing
        if item.get("name", "").startswith("auto-shop-owned::")
    ]
    owned_names = [item["name"] for item in owned]
    if len(owned_names) != len(set(owned_names)):
        raise ProvisioningError("Owned alert condition discovery was ambiguous")
    expected_names = {condition["name"] for condition in alerts["conditions"]}
    if set(owned_names) - expected_names:
        raise ProvisioningError("Unexpected owned alert conditions require manual review")
    by_name = {item["name"]: item for item in owned}
    for condition in alerts["conditions"]:
        condition_input = _condition_input(condition, enabled=action == "apply")
        current = by_name.get(condition["name"])
        if current:
            client.execute(
                CONDITION_UPDATE,
                {
                    "accountId": account_id,
                    "conditionId": current["id"],
                    "condition": condition_input,
                },
            )
        elif action == "apply":
            client.execute(
                CONDITION_CREATE,
                {
                    "accountId": account_id,
                    "policyId": policy_id,
                    "condition": condition_input,
                },
            )
    return {
        **coverage_summary,
        "dashboard": (
            "unchanged"
            if action == "disable"
            else "updated" if dashboards else "created"
        ),
        "policy": "reconciled",
        "conditions": len(alerts["conditions"]),
        "notifications": "not-attached",
        "enabled": action == "apply",
    }


def main(argv: list[str] | None = None, *, environ: Mapping[str, str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("validate", "plan", "apply", "disable"))
    parser.add_argument("--profile", choices=("technical", "service-order"), default="technical")
    parser.add_argument("--dashboard", type=Path, required=True)
    parser.add_argument("--alerts", type=Path, required=True)
    parser.add_argument("--region", choices=tuple(ENDPOINTS), default="us")
    arguments = parser.parse_args(argv)
    environment = os.environ if environ is None else environ
    try:
        dashboard = _load_json(arguments.dashboard)
        alerts = _load_json(arguments.alerts)
        if arguments.profile == "service-order":
            validate_service_order_definitions(dashboard, alerts)
        else:
            validate_definitions(dashboard, alerts)
        if arguments.action == "validate":
            if arguments.profile == "service-order":
                total_widgets = sum(len(page["widgets"]) for page in dashboard["pages"])
                eligible_widgets = total_widgets
                total_conditions = len(alerts["conditions"])
                eligible_conditions = total_conditions
            else:
                _, total_widgets, eligible_widgets = _verified_dashboard_subset(dashboard)
                _, total_conditions, eligible_conditions = _verified_alerts_subset(alerts)
            result = {
                "conditions": total_conditions,
                "eligible_conditions": eligible_conditions,
                "eligible_widgets": eligible_widgets,
                "excluded_conditions": total_conditions - eligible_conditions,
                "excluded_widgets": total_widgets - eligible_widgets,
                "status": "valid",
                "widgets": total_widgets,
            }
        else:
            account_id = _positive_account_id(environment.get("NEW_RELIC_ACCOUNT_ID", ""))
            client = NerdGraphClient(
                api_key=environment.get("NEW_RELIC_USER_API_KEY", ""),
                region=arguments.region,
            )
            result = reconcile(
                client,
                account_id,
                dashboard,
                alerts,
                action=arguments.action,
                profile=arguments.profile,
            )
    except (TypeError, ValueError, ProvisioningError) as error:
        print(str(error), file=sys.stderr)
        return 1
    print(json.dumps(result, separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
