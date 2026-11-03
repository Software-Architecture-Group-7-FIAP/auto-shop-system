import json
from copy import deepcopy
from pathlib import Path

import pytest

import scripts.observability.provision_technical_observability as technical_observability
from scripts.observability.provision_technical_observability import (
    CONDITION_CREATE,
    CONDITION_SEARCH,
    DASHBOARD_CREATE,
    DASHBOARD_SEARCH,
    DASHBOARD_UPDATE,
    POLICY_CREATE,
    POLICY_SEARCH,
    TAG_ENTITY,
    NerdGraphClient,
    ProvisioningError,
    _condition_input,
    _dashboard_input,
    _dashboard_mutation_guid,
    _entities,
    _has_ownership_tag,
    _verified_alerts_subset,
    main,
    reconcile,
    validate_definitions,
)

ROOT = Path(__file__).resolve().parents[3]
DASHBOARD_PATH = ROOT / "observability" / "new-relic" / "technical-dashboard.json"
ALERTS_PATH = ROOT / "observability" / "new-relic" / "technical-alerts.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_dashboard_has_required_aggregate_widgets_and_metadata():
    dashboard = _load(DASHBOARD_PATH)
    alerts = _load(ALERTS_PATH)

    validate_definitions(dashboard, alerts)
    widgets = [widget for page in dashboard["pages"] for widget in page["widgets"]]
    assert len(widgets) == 11
    assert len({widget["id"] for widget in widgets}) == 11
    assert "aws_schema_mapping" not in dashboard
    assert {widget["coverage_status"] for widget in widgets} == {
        "verified",
        "excluded",
        "gated",
    }
    excluded_gateway = next(widget for widget in widgets if widget["id"] == "gateway-volume-errors")
    assert excluded_gateway["coverage_status"] == "excluded"
    assert "HTTP API v2" in excluded_gateway["coverage_note"]
    gated_lambda = next(widget for widget in widgets if widget["id"] == "lambda-auth-health")
    assert gated_lambda["coverage_status"] == "gated"
    assert "schema" in gated_lambda["coverage_note"].lower()
    for widget in widgets:
        assert widget["time_range"] == "30 minutes"
        assert widget["unit"]
        assert widget["filters"]
        query = widget["nrql"].lower()
        assert "select *" not in query
        assert " from log " not in f" {query} "
        assert " since 30 minutes ago" in query


def test_dashboard_replacement_uses_v2_identity_and_keeps_alert_policy_name():
    dashboard = _load(DASHBOARD_PATH)
    alerts = _load(ALERTS_PATH)

    assert dashboard["name"] == "auto-shop-owned::HML Technical Health v2"
    assert dashboard["ownership"] == "auto-shop-owned-hml-technical-v2"
    assert alerts["ownership"] == dashboard["ownership"]
    assert alerts["policy"]["name"] == "auto-shop-owned::HML Technical Alerts"


def test_validate_reports_dashboard_and_alert_counts(capsys):
    result = main(
        [
            "validate",
            "--dashboard",
            str(DASHBOARD_PATH),
            "--alerts",
            str(ALERTS_PATH),
        ]
    )

    assert result == 0
    assert json.loads(capsys.readouterr().out) == {
        "conditions": 7,
        "eligible_conditions": 7,
        "eligible_widgets": 7,
        "excluded_conditions": 0,
        "excluded_widgets": 4,
        "status": "valid",
        "widgets": 11,
    }


def test_dashboard_and_alert_queries_exclude_personal_and_raw_fields():
    definitions = json.dumps(
        {"dashboard": _load(DASHBOARD_PATH), "alerts": _load(ALERTS_PATH)}
    ).lower()
    forbidden = (
        "select *",
        "latest(message)",
        "correlation_id",
        "trace.id",
        "span.id",
        "service_order_id",
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


def test_alerts_cover_api_and_kubernetes_with_complete_operational_metadata():
    alerts = _load(ALERTS_PATH)
    conditions = alerts["conditions"]
    assert len(conditions) == 7
    assert {condition["category"] for condition in conditions} == {
        "api_availability",
        "api_latency",
        "api_error_rate",
        "k8s_readiness",
        "k8s_restarts",
        "k8s_cpu",
        "k8s_memory",
    }
    assert alerts["notification_route"]["attach_by_default"] is False
    assert "workflow_id" not in json.dumps(alerts["notification_route"]).lower()
    for condition in conditions:
        assert condition["enabled_during_hml_only"] is True
        assert condition["loss_of_signal"]["enabled"] is False
        assert condition["signal"]["aggregation_window_seconds"] in {60, 300}
        assert condition["terms"]
        assert condition["runbook_url"].startswith(
            "https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/"
        )


def test_unsupported_and_unverified_sources_cannot_be_claimed_as_verified():
    dashboard = _load(DASHBOARD_PATH)
    alerts = _load(ALERTS_PATH)

    for widget_id in ("gateway-volume-errors", "lambda-auth-health"):
        unsafe_dashboard = deepcopy(dashboard)
        widget = next(
            widget
            for page in unsafe_dashboard["pages"]
            for widget in page["widgets"]
            if widget["id"] == widget_id
        )
        widget["coverage_status"] = "verified"

        with pytest.raises(ValueError, match="coverage status"):
            validate_definitions(unsafe_dashboard, alerts)

    unsafe_alerts = deepcopy(alerts)
    gated_condition = unsafe_alerts["conditions"][0]
    gated_condition["coverage_status"] = "gated"

    with pytest.raises(ValueError, match="coverage status"):
        validate_definitions(dashboard, unsafe_alerts)


def test_unsupported_widgets_cannot_be_laundered_through_a_verified_source():
    dashboard = _load(DASHBOARD_PATH)
    alerts = _load(ALERTS_PATH)

    for widget_id in ("gateway-volume-errors", "lambda-auth-health"):
        unsafe_dashboard = deepcopy(dashboard)
        widget = next(
            widget
            for page in unsafe_dashboard["pages"]
            for widget in page["widgets"]
            if widget["id"] == widget_id
        )
        widget["source"] = "Transaction"
        widget["coverage_status"] = "verified"
        widget["nrql"] = (
            "FROM Transaction SELECT count(*) "
            "WHERE appName = 'auto-shop-api' AND label.environment = 'hml' "
            "SINCE 30 minutes ago"
        )

        with pytest.raises(ValueError, match="source does not match"):
            validate_definitions(unsafe_dashboard, alerts)

    unsafe_alerts = deepcopy(alerts)
    condition = unsafe_alerts["conditions"][0]
    condition["source"] = "ServerlessSample"
    condition["coverage_status"] = "gated"
    condition["nrql"] = (
        "FROM ServerlessSample SELECT count(*) "
        "WHERE provider.functionName = 'lambda-auth-hml'"
    )

    with pytest.raises(ValueError, match="source does not match"):
        validate_definitions(dashboard, unsafe_alerts)


def test_verified_sources_require_their_hml_scope_in_dashboard_and_alert_queries():
    dashboard = _load(DASHBOARD_PATH)
    alerts = _load(ALERTS_PATH)
    unsafe_dashboard = deepcopy(dashboard)
    unsafe_dashboard["pages"][0]["widgets"][0]["nrql"] = (
        "FROM Transaction SELECT rate(count(*), 1 minute) "
        "WHERE appName = 'auto-shop-api' SINCE 30 minutes ago"
    )

    with pytest.raises(ValueError, match="HML scope"):
        validate_definitions(unsafe_dashboard, alerts)

    unsafe_alerts = deepcopy(alerts)
    unsafe_alerts["conditions"][0]["nrql"] = (
        "FROM Transaction SELECT percentage(count(*), WHERE error IS false) "
        "WHERE appName = 'auto-shop-api'"
    )

    with pytest.raises(ValueError, match="HML scope"):
        validate_definitions(dashboard, unsafe_alerts)

    unsafe_dashboard["pages"][0]["widgets"][0]["nrql"] = (
        "FROM Transaction SELECT rate(count(*), 1 minute) "
        "WHERE appName = 'auto-shop-api' AND label.environment = 'hml' "
        "OR appName = 'production-api' SINCE 30 minutes ago"
    )

    with pytest.raises(ValueError, match="HML scope"):
        validate_definitions(unsafe_dashboard, alerts)


def test_dashboard_discovery_fails_closed_when_nerdgraph_response_is_malformed():
    with pytest.raises(ProvisioningError, match="dashboard discovery response was invalid"):
        _entities(
            {
                "actor": {
                    "entitySearch": {
                        "results": {"entities": None},
                    }
                }
            }
        )


def test_dashboard_ownership_requires_an_exact_structured_tag_value():
    ownership = "auto-shop-owned-hml-technical-v2"

    assert _has_ownership_tag(
        {
            "tags": [
                {
                    "key": "auto-shop.ownership",
                    "values": [ownership],
                }
            ]
        },
        ownership,
    )
    assert not _has_ownership_tag(
        {
            "tags": [
                {
                    "key": "auto-shop.ownership",
                    "values": f"prefix-{ownership}-suffix",
                }
            ]
        },
        ownership,
    )


def test_explicitly_gated_alert_condition_is_excluded_from_reconciliation():
    alerts = _load(ALERTS_PATH)
    gated_condition = alerts["conditions"][0]
    gated_condition["source"] = "ServerlessSample"
    gated_condition["coverage_status"] = "gated"
    gated_condition["coverage_note"] = "Gated until the Lambda schema is verified."
    gated_condition["nrql"] = (
        "FROM ServerlessSample SELECT count(*) "
        "WHERE provider.functionName = 'lambda-auth-hml'"
    )

    verified_alerts, total, eligible = _verified_alerts_subset(alerts)

    assert total == 7
    assert eligible == 6
    assert len(verified_alerts["conditions"]) == 6
    assert all(
        condition["source"] != "ServerlessSample"
        for condition in verified_alerts["conditions"]
    )


def test_nerdgraph_client_uses_fixed_endpoint_header_and_bounded_safe_errors():
    captured = {}

    class _Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def read(self, size):
            captured["read_size"] = size
            return b'{"data":{"ok":true}}'

    def opener(request, timeout):
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        captured["body"] = json.loads(request.data)
        captured["timeout"] = timeout
        return _Response()

    client = NerdGraphClient(api_key="NRAK-secret-value", region="us", opener=opener)
    result = client.execute("query Fixed($accountId:Int!){actor{account(id:$accountId){id}}}", {"accountId": 1})

    assert result == {"ok": True}
    assert captured["url"] == "https://api.newrelic.com/graphql"
    assert captured["headers"]["Api-key"] == "NRAK-secret-value"
    assert "NRAK-secret-value" not in json.dumps(captured["body"])
    assert captured["read_size"] <= 1_048_577
    assert captured["timeout"] == 10


def test_nerdgraph_graphql_errors_are_sanitized():
    class _Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def read(self, _size):
            return (
                b'{"errors":[{"message":"Field \'expirationDuration\' is not '
                b'defined by type \'AlertsNrqlConditionStaticInput\'. Value '
                b'\'NRAK-secret-value\' came from account 123456789 and '
                b'entity 123e4567-e89b-12d3-a456-426614174000.","path":'
                b'["actor","account","alerts","alertsNrqlConditionStaticCreate"]}]}'
            )

    client = NerdGraphClient(
        api_key="NRAK-secret",
        region="us",
        opener=lambda *_args, **_kwargs: _Response(),
    )
    with pytest.raises(ProvisioningError, match="NerdGraph rejected the operation") as error:
        client.execute("mutation CreateCondition{actor{account{id}}}", {})

    diagnostic = str(error.value)
    assert "expirationDuration" in diagnostic
    assert "AlertsNrqlConditionStaticInput" in diagnostic
    assert "actor.account.alerts.alertsNrqlConditionStaticCreate" in diagnostic
    assert "NRAK-secret-value" not in diagnostic
    assert "123456789" not in diagnostic
    assert "123e4567-e89b-12d3-a456-426614174000" not in diagnostic


@pytest.mark.parametrize(
    ("message", "category", "extensions", "expected_identifiers"),
    [
        (
            "You are not authorized to update the dashboard",
            "authorization",
            {"code": "FORBIDDEN", "errorType": "ACCESS_DENIED"},
            ("code=FORBIDDEN", "errorType=ACCESS_DENIED"),
        ),
        (
            "Dashboard does not exist",
            "not-found",
            {"code": "RESOURCE-8684974", "errorType": "DASHBOARD_123456"},
            (),
        ),
        (
            "Dashboard input is invalid",
            "validation",
            {"code": "BAD_USER_INPUT", "errorType": "VALIDATION_ERROR"},
            ("code=BAD_USER_INPUT", "errorType=VALIDATION_ERROR"),
        ),
        (
            "upstream rejected token NRAK-secret-value",
            None,
            {"code": "CUSTOM_SECRET_CODE", "errorType": "PRIVATE_RESOURCE_ID"},
            (),
        ),
    ],
)
def test_nerdgraph_top_level_errors_report_safe_categories_only(
    message, category, extensions, expected_identifiers
):
    payload = {
        "errors": [
            {
                "message": (
                    f"{message}; account 8684974; entity "
                    "123e4567-e89b-12d3-a456-426614174000; "
                    "dashboard private-dashboard-guid private-dashboard-name; "
                    "credential NRAK-secret-value"
                ),
                "path": ["dashboardUpdate"] if category else [],
                "extensions": {**extensions, "traceId": "trace-secret"},
            }
        ]
    }

    class _Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def read(self, _size):
            return json.dumps(payload).encode("utf-8")

    client = NerdGraphClient(
        api_key="NRAK-secret-value",
        region="us",
        opener=lambda *_args, **_kwargs: _Response(),
    )
    with pytest.raises(ProvisioningError) as error:
        client.execute(
            "mutation UpdateDashboard($guid: EntityGuid!, $dashboard: DashboardUpdateInput!) "
            "{ dashboardUpdate(guid: $guid, dashboard: $dashboard) { entityResult { guid } } }",
            {"guid": "private-dashboard-guid", "dashboard": {"name": "private-dashboard-name"}},
        )

    diagnostic = str(error.value)
    if category:
        assert f"category={category}" in diagnostic
        assert "path: dashboardUpdate" in diagnostic
    else:
        assert "GraphQL details redacted" in diagnostic
    assert all(identifier in diagnostic for identifier in expected_identifiers)
    assert not any(
        value in diagnostic
        for value in (
            "NRAK-secret-value",
            "8684974",
            "123e4567-e89b-12d3-a456-426614174000",
            "private-dashboard-guid",
            "private-dashboard-name",
            "trace-secret",
            "CUSTOM_SECRET_CODE",
            "PRIVATE_RESOURCE_ID",
        )
    )


def test_workflow_is_manual_gated_and_does_not_version_notification_destination():
    workflow = (ROOT / ".github" / "workflows" / "new-relic-hml-technical.yml").read_text(
        encoding="utf-8"
    )
    assert "workflow_dispatch:" in workflow
    assert "github.ref == 'refs/heads/develop'" in workflow
    assert "environment: hml" in workflow
    assert "contents: read" in workflow
    assert 'validate_environment_window.py --action "$validator_action"' in workflow
    assert "validator_action=teardown" in workflow
    assert "NEW_RELIC_USER_API_KEY" in workflow
    assert "NEW_RELIC_LICENSE_KEY" not in workflow
    assert "confirm_apply" in workflow
    assert "confirm_notification_route" in workflow
    assert "session_token:" in workflow
    assert "LIFECYCLE_SESSION_TOKEN" in workflow
    assert "LIFECYCLE_SESSION_SIGNING_KEY" in workflow
    assert "STAGING_SESSION_AUTHORIZED" in workflow
    assert "SESSION_MODE" in workflow
    assert "validator_action=teardown" in workflow
    assert "confirm_aws_schema" not in workflow
    assert "CONFIRM_AWS_SCHEMA" not in workflow
    assert "--confirm-aws-schema" not in workflow
    assert "persist-credentials: false" in workflow


def test_apply_reconciles_only_the_verified_fastapi_and_kubernetes_subset(monkeypatch, capsys):
    class _Client:
        def __init__(self):
            self.dashboard_input = None
            self.created_conditions = []

        def execute(self, document, variables):
            if document == DASHBOARD_SEARCH:
                return {"actor": {"entitySearch": {"results": {"entities": []}}}}
            if document == DASHBOARD_CREATE:
                self.dashboard_input = variables["dashboard"]
                return {
                    "dashboardCreate": {
                        "entityResult": {"guid": "dashboard-guid"},
                        "errors": [],
                    }
                }
            if document == TAG_ENTITY:
                return {"taggingAddTagsToEntity": {"errors": []}}
            if document == POLICY_SEARCH:
                return {
                    "actor": {
                        "account": {"alerts": {"policiesSearch": {"policies": []}}}
                    }
                }
            if document == POLICY_CREATE:
                return {"alertsPolicyCreate": {"id": "7"}}
            if document == CONDITION_SEARCH:
                return {
                    "actor": {
                        "account": {
                            "alerts": {"nrqlConditionsSearch": {"nrqlConditions": []}}
                        }
                    }
                }
            if document == CONDITION_CREATE:
                self.created_conditions.append(variables["condition"])
                return {"alertsNrqlConditionStaticCreate": {"id": "condition-id"}}
            raise AssertionError("apply issued an unexpected NerdGraph operation")

    client = _Client()
    monkeypatch.setattr(technical_observability, "NerdGraphClient", lambda **_kwargs: client)

    result = main(
        [
            "apply",
            "--dashboard",
            str(DASHBOARD_PATH),
            "--alerts",
            str(ALERTS_PATH),
        ],
        environ={"NEW_RELIC_ACCOUNT_ID": "1", "NEW_RELIC_USER_API_KEY": "test-key"},
    )

    assert result == 0
    output = json.loads(capsys.readouterr().out)
    assert output["eligible_widgets"] == 7
    assert output["excluded_widgets"] == 4
    assert output["eligible_conditions"] == 7
    assert output["excluded_conditions"] == 0
    applied_widgets = [
        widget
        for page in client.dashboard_input["pages"]
        for widget in page["widgets"]
    ]
    assert len(applied_widgets) == 7
    assert len(client.created_conditions) == 7
    applied_nrql = json.dumps(client.dashboard_input).lower()
    assert "apigateway" not in applied_nrql
    assert "serverlesssample" not in applied_nrql
    assert "provider.functionname" not in applied_nrql
    assert "from transaction" in applied_nrql
    assert "from k8spodsample" in applied_nrql
    assert "from k8scontainersample" in applied_nrql
    assert "from k8shpasample" in applied_nrql


def test_reconcile_revalidates_contracts_and_rejects_unknown_profiles_before_network_calls():
    dashboard = _load(DASHBOARD_PATH)
    alerts = _load(ALERTS_PATH)
    gateway = next(
        widget
        for page in dashboard["pages"]
        for widget in page["widgets"]
        if widget["id"] == "gateway-volume-errors"
    )
    gateway["source"] = "Transaction"
    gateway["coverage_status"] = "verified"
    gateway["nrql"] = (
        "FROM Transaction SELECT count(*) "
        "WHERE appName = 'auto-shop-api' AND label.environment = 'hml'"
    )

    class _Client:
        def __init__(self):
            self.documents = []

        def execute(self, document, _variables):
            self.documents.append(document)
            return {}

    client = _Client()
    with pytest.raises(ValueError, match="source does not match"):
        reconcile(client, 1, dashboard, alerts, action="apply")
    assert client.documents == []

    dashboard = _load(DASHBOARD_PATH)
    with pytest.raises(ValueError, match="profile"):
        reconcile(
            client,
            1,
            dashboard,
            alerts,
            action="apply",
            profile="unsupported",
        )
    assert client.documents == []


def test_plan_is_read_only_and_idempotently_counts_owned_resources():
    dashboard = _load(DASHBOARD_PATH)
    alerts = _load(ALERTS_PATH)

    class _Client:
        def __init__(self):
            self.documents = []

        def execute(self, document, variables):
            self.documents.append(document)
            if document == DASHBOARD_SEARCH:
                return {
                    "actor": {
                        "entitySearch": {
                            "results": {
                                "entities": [
                                    {
                                        "guid": "dashboard-guid",
                                        "name": dashboard["name"],
                                        "type": "DASHBOARD",
                                        "accountId": 1,
                                        "tags": [
                                            {
                                                "key": "auto-shop.ownership",
                                                "values": [dashboard["ownership"]],
                                            }
                                        ],
                                    }
                                ]
                            }
                        }
                    }
                }
            if document == POLICY_SEARCH:
                return {
                    "actor": {
                        "account": {
                            "alerts": {
                                "policiesSearch": {
                                    "policies": [{"id": "7", "name": alerts["policy"]["name"]}]
                                }
                            }
                        }
                    }
                }
            if document == CONDITION_SEARCH:
                return {
                    "actor": {
                        "account": {
                            "alerts": {
                                "nrqlConditionsSearch": {
                                    "nrqlConditions": [
                                        {"id": "9", "name": alerts["conditions"][0]["name"]}
                                    ]
                                }
                            }
                        }
                    }
                }
            raise AssertionError("plan attempted a mutation")

    client = _Client()
    result = reconcile(client, 1, dashboard, alerts, action="plan")

    assert result["dashboard"] == "update"
    assert result["policy"] == "update"
    assert result["eligible_widgets"] == 7
    assert result["excluded_widgets"] == 4
    assert result["eligible_conditions"] == 7
    assert result["excluded_conditions"] == 0
    assert result["conditions_update"] == 1
    assert result["conditions_create"] == 6
    assert client.documents == [DASHBOARD_SEARCH, POLICY_SEARCH, CONDITION_SEARCH]

    repeated_client = _Client()
    repeated_result = reconcile(
        repeated_client,
        1,
        dashboard,
        alerts,
        action="plan",
    )

    assert repeated_result == result
    assert repeated_client.documents == client.documents


def test_runbook_documents_sources_thresholds_route_drills_and_teardown():
    runbook = (
        ROOT / "docs" / "observability" / "new-relic-technical-dashboard-alerts.md"
    ).read_text(encoding="utf-8")
    lowered = runbook.lower()

    for value in (
        "apigatewaysample",
        "serverlesssample",
        "k8spodsample",
        "severity",
        "notification route",
        "controlled drills",
        "lifecycle teardown",
        "2026-10-31",
    ):
        assert value in lowered


def test_dashboard_update_preserves_page_widget_ids_and_uses_current_input_shape():
    dashboard = _load(DASHBOARD_PATH)
    first_page = dashboard["pages"][0]
    first_widget = first_page["widgets"][0]
    rendered = _dashboard_input(
        dashboard,
        123,
        {
            "pages": [
                {
                    "guid": "page-guid",
                    "name": first_page["name"],
                    "widgets": [{"id": "widget-id", "title": first_widget["title"]}],
                }
            ]
        },
    )

    assert "DashboardUpdateInput!" in DASHBOARD_UPDATE
    assert rendered["pages"][0]["guid"] == "page-guid"
    assert rendered["pages"][0]["widgets"][0]["id"] == "widget-id"
    query = rendered["pages"][0]["widgets"][0]["rawConfiguration"]["nrqlQueries"][0]
    assert query["accountIds"] == [123]
    assert "accountId" not in query


def test_alert_expiration_shape_and_dashboard_business_errors_fail_closed():
    alerts = _load(ALERTS_PATH)
    rendered = _condition_input(alerts["conditions"][0], enabled=True)
    assert "expiration" in rendered
    assert "closeViolationsOnExpiration" not in rendered

    with pytest.raises(ProvisioningError, match="mutation was rejected"):
        _dashboard_mutation_guid(
            {
                "dashboardUpdate": {
                    "entityResult": {"guid": "ignored"},
                    "errors": [{"type": "INVALID_INPUT"}],
                }
            },
            "dashboardUpdate",
        )


def test_validation_rejects_whitespace_raw_query_and_malformed_threshold():
    dashboard = _load(DASHBOARD_PATH)
    alerts = _load(ALERTS_PATH)
    unsafe_dashboard = deepcopy(dashboard)
    unsafe_dashboard["pages"][0]["widgets"][0]["nrql"] = (
        "FROM\nLog SELECT   * WHERE service = 'auto-shop-api' SINCE 30 minutes ago"
    )
    with pytest.raises(ValueError, match="privacy contract"):
        validate_definitions(unsafe_dashboard, alerts)

    unsafe_dashboard = deepcopy(dashboard)
    unsafe_dashboard["pages"][0]["widgets"][0]["nrql"] = (
        "FROM Transaction SELECT count(cpf) "
        "WHERE appName = 'auto-shop-api' AND label.environment = 'hml' "
        "SINCE 30 minutes ago"
    )
    with pytest.raises(ValueError, match="privacy contract"):
        validate_definitions(unsafe_dashboard, alerts)

    unsafe_alerts = deepcopy(alerts)
    unsafe_alerts["conditions"][0]["terms"][0]["threshold"] = -1
    with pytest.raises(ValueError, match="threshold"):
        validate_definitions(dashboard, unsafe_alerts)

    duplicate_widget_title = deepcopy(dashboard)
    duplicate_widget_title["pages"][0]["widgets"][1]["title"] = (
        duplicate_widget_title["pages"][0]["widgets"][0]["title"]
    )
    with pytest.raises(ValueError, match="duplicate dashboard widget title"):
        validate_definitions(duplicate_widget_title, alerts)

    duplicate_condition_name = deepcopy(alerts)
    duplicate_condition_name["conditions"][1]["name"] = duplicate_condition_name[
        "conditions"
    ][0]["name"]
    with pytest.raises(ValueError, match="Duplicate alert condition name"):
        validate_definitions(dashboard, duplicate_condition_name)
