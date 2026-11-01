import json
from copy import deepcopy
from pathlib import Path

import pytest

from scripts.observability.provision_technical_observability import (
    CONDITION_SEARCH,
    DASHBOARD_UPDATE,
    DASHBOARD_SEARCH,
    NerdGraphClient,
    POLICY_SEARCH,
    ProvisioningError,
    reconcile,
    _condition_input,
    _dashboard_input,
    _dashboard_mutation_guid,
    main,
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

    validate_definitions(dashboard, alerts, require_verified_aws=False)
    widgets = [widget for page in dashboard["pages"] for widget in page["widgets"]]
    assert len(widgets) == 11
    assert len({widget["id"] for widget in widgets}) == 11
    required_sources = {
        "Transaction",
        "ApiGatewaySample",
        "ServerlessSample",
        "K8sPodSample",
        "K8sContainerSample",
        "K8sHpaSample",
    }
    assert required_sources <= {widget["source"] for widget in widgets}
    gateway_availability = next(
        widget for widget in widgets if widget["id"] == "gateway-error-availability"
    )
    assert gateway_availability["source"] == "ApiGatewaySample"
    assert gateway_availability["unit"] == "percent"
    gateway_query = gateway_availability["nrql"].lower()
    assert "sum(provider.count)" in gateway_query
    assert "sum(provider.4xxerror)" in gateway_query
    assert "sum(provider.5xxerror)" in gateway_query
    assert "availability" in gateway_query
    assert "4xx error rate" in gateway_query
    assert "5xx error rate" in gateway_query
    for widget in widgets:
        assert widget["time_range"] == "30 minutes"
        assert widget["unit"]
        assert widget["filters"]
        query = widget["nrql"].lower()
        assert "select *" not in query
        assert " from log " not in f" {query} "
        assert " since 30 minutes ago" in query


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


def test_apply_refuses_unverified_aws_schema():
    dashboard = _load(DASHBOARD_PATH)
    alerts = _load(ALERTS_PATH)

    with pytest.raises(ValueError, match="AWS schema mapping"):
        validate_definitions(dashboard, alerts, require_verified_aws=True)


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
            return b'{"errors":[{"message":"echo NRAK-secret and query"}]}'

    client = NerdGraphClient(
        api_key="NRAK-secret",
        region="us",
        opener=lambda *_args, **_kwargs: _Response(),
    )
    with pytest.raises(ProvisioningError, match="NerdGraph rejected the operation") as error:
        client.execute("query Fixed{actor{user{id}}}", {})

    assert "secret" not in str(error.value).lower()


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
    assert "persist-credentials: false" in workflow


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
    assert result["conditions_update"] == 1
    assert result["conditions_create"] == 6
    assert client.documents == [DASHBOARD_SEARCH, POLICY_SEARCH, CONDITION_SEARCH]


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
        validate_definitions(unsafe_dashboard, alerts, require_verified_aws=False)

    unsafe_alerts = deepcopy(alerts)
    unsafe_alerts["conditions"][0]["terms"][0]["threshold"] = -1
    with pytest.raises(ValueError, match="threshold"):
        validate_definitions(dashboard, unsafe_alerts, require_verified_aws=False)
