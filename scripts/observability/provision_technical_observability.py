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
        NerdGraphClient,
        ProvisioningError,
        TAG_ENTITY,
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
        NerdGraphClient,
        ProvisioningError,
        TAG_ENTITY,
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
)

SERVICE_ORDER_OWNERSHIP = "auto-shop-owned-hml-service-order-v1"
SERVICE_ORDER_DASHBOARD_NAME = "auto-shop-owned::HML Service Order Operations"
SERVICE_ORDER_POLICY_NAME = "auto-shop-owned::HML Service Order Failures"
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


def validate_definitions(
    dashboard: dict,
    alerts: dict,
    *,
    require_verified_aws: bool,
) -> None:
    _require_exact_keys(
        dashboard,
        {
            "schema_version",
            "ownership",
            "name",
            "description",
            "permissions",
            "aws_schema_mapping",
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
    mapping = dashboard.get("aws_schema_mapping")
    if not isinstance(mapping, dict) or set(mapping) != {
        "verified",
        "verified_at",
        "evidence_run_url",
    }:
        raise ValueError("Invalid AWS schema mapping")
    if require_verified_aws and mapping.get("verified") is not True:
        raise ValueError("AWS schema mapping must be verified before apply")
    if mapping.get("verified") is True:
        verified_at = mapping.get("verified_at")
        evidence_url = mapping.get("evidence_run_url")
        if not isinstance(verified_at, str) or not re.fullmatch(
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z",
            verified_at,
        ):
            raise ValueError("Invalid AWS schema verification timestamp")
        if not isinstance(evidence_url, str) or not evidence_url.startswith(
            "https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/actions/runs/"
        ):
            raise ValueError("Invalid AWS schema evidence URL")
    pages = dashboard.get("pages")
    if not isinstance(pages, list) or len(pages) != 2:
        raise ValueError("Dashboard must contain exactly two pages")
    widget_ids: set[str] = set()
    widget_count = 0
    for page in pages:
        _require_exact_keys(page, {"name", "widgets"}, "dashboard page")
        if not isinstance(page.get("widgets"), list):
            raise ValueError("Dashboard page widgets must be a list")
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
                    "nrql",
                },
                "dashboard widget",
            )
            widget_id = widget.get("id")
            if not isinstance(widget_id, str) or not SAFE_ID_PATTERN.fullmatch(widget_id):
                raise ValueError("Invalid dashboard widget ID")
            if widget_id in widget_ids:
                raise ValueError("Duplicate dashboard widget ID")
            widget_ids.add(widget_id)
            if widget.get("visualization") not in {"line", "billboard"}:
                raise ValueError("Invalid dashboard visualization")
            if widget.get("time_range") != "30 minutes":
                raise ValueError("Invalid dashboard time range")
            if not isinstance(widget.get("filters"), list) or not widget["filters"]:
                raise ValueError("Dashboard widget filters are required")
            source = widget.get("source")
            if source not in {
                "Transaction",
                "ApiGatewaySample",
                "ServerlessSample",
                "K8sPodSample",
                "K8sContainerSample",
                "K8sHpaSample",
            }:
                raise ValueError("Invalid dashboard source")
            for field_name in ("title", "unit"):
                field_value = widget.get(field_name)
                if not isinstance(field_value, str) or not 1 <= len(field_value) <= 120:
                    raise ValueError("Invalid dashboard display field")
            _validate_query(widget.get("nrql"), bounded=True, expected_source=source)
            widget_count += 1
    if widget_count != 11:
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
                "loss_of_signal",
                "enabled_during_hml_only",
                "runbook_url",
            },
            "alert condition",
        )
        condition_id = condition.get("id")
        if not isinstance(condition_id, str) or not SAFE_ID_PATTERN.fullmatch(condition_id):
            raise ValueError("Invalid alert condition ID")
        if condition_id in condition_ids:
            raise ValueError("Duplicate alert condition ID")
        condition_ids.add(condition_id)
        if not RESOURCE_NAME_PATTERN.fullmatch(str(condition.get("name", ""))):
            raise ValueError("Invalid owned alert condition name")
        source = condition.get("source")
        if source not in {"Transaction", "K8sPodSample", "K8sContainerSample"}:
            raise ValueError("Invalid alert source")
        _validate_query(condition.get("nrql"), bounded=False, expected_source=source)
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
        raise ValueError("Observability definition must be a JSON object")
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
        "expiration": {
            "closeViolationsOnExpiration": True,
            "expirationDuration": None,
            "openViolationOnExpiration": False,
        },
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
    return values if isinstance(values, list) else []


def _has_ownership_tag(entity: dict, ownership: str) -> bool:
    return any(
        tag.get("key") == "auto-shop.ownership" and ownership in tag.get("values", [])
        for tag in entity.get("tags", [])
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
) -> dict[str, object]:
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
            "dashboard": "update" if dashboards else "create",
            "policy": "update",
            "conditions_create": len(expected_names - owned_names),
            "conditions_update": len(expected_names & owned_names),
            "notifications": "not-attached",
        }
    if not policies:
        if action == "disable":
            return {"dashboard": "unchanged", "policy": "absent", "conditions": 0}
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
    parser.add_argument("--confirm-aws-schema", action="store_true")
    arguments = parser.parse_args(argv)
    environment = os.environ if environ is None else environ
    try:
        dashboard = _load_json(arguments.dashboard)
        alerts = _load_json(arguments.alerts)
        require_verified = arguments.action == "apply" and arguments.profile == "technical"
        if arguments.profile == "service-order":
            validate_service_order_definitions(dashboard, alerts)
        else:
            validate_definitions(
                dashboard,
                alerts,
                require_verified_aws=require_verified and arguments.confirm_aws_schema,
            )
        if require_verified and not arguments.confirm_aws_schema:
            raise ValueError("Apply requires --confirm-aws-schema")
        if arguments.action == "validate":
            result = {
                "status": "valid",
                "widgets": sum(len(page["widgets"]) for page in dashboard["pages"]),
                "conditions": len(alerts["conditions"]),
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
            )
    except (ValueError, ProvisioningError) as error:
        print(str(error), file=sys.stderr)
        return 1
    print(json.dumps(result, separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
