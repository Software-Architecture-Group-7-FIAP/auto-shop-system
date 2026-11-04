import json
from copy import deepcopy
from pathlib import Path

import pytest

from scripts.observability.provision_technical_observability import (
    CONDITION_CREATE,
    CONDITION_DELETE,
    CONDITION_GET,
    CONDITION_SEARCH,
    CONDITION_UPDATE,
    DASHBOARD_CREATE,
    DASHBOARD_GET,
    DASHBOARD_SEARCH,
    DASHBOARD_UPDATE,
    POLICY_CREATE,
    POLICY_SEARCH,
    POLICY_UPDATE,
    TAG_ENTITY,
    _dashboard_input,
    reconcile,
)

ROOT = Path(__file__).resolve().parents[3]
OBSERVABILITY = ROOT / "observability" / "new-relic"
ACCOUNT_ID = 8_684_974
PROFILE_FILES = (
    pytest.param(
        "technical",
        "technical-dashboard.json",
        "technical-alerts.json",
        id="technical",
    ),
    pytest.param(
        "service-order",
        "service-order-dashboard.json",
        "service-order-alerts.json",
        id="service-order",
    ),
)


def _load_definition(filename: str) -> dict:
    return json.loads((OBSERVABILITY / filename).read_text(encoding="utf-8"))


def _expected_dashboard_input(dashboard: dict, account_id: int) -> dict:
    pages = []
    for page in dashboard["pages"]:
        widgets = []
        for index, widget in enumerate(page["widgets"]):
            widgets.append(
                {
                    "title": widget["title"],
                    "visualization": {"id": f"viz.{widget['visualization']}"},
                    "layout": {
                        "row": (index // 2) * 3 + 1,
                        "column": 1 if index % 2 == 0 else 7,
                        "width": 6,
                        "height": 3,
                    },
                    "linkedEntityGuids": [],
                    "rawConfiguration": {
                        "nrqlQueries": [
                            {"accountIds": [account_id], "query": widget["nrql"]}
                        ]
                    },
                }
            )
        pages.append({"name": page["name"], "widgets": widgets})
    return {
        "name": dashboard["name"],
        "description": dashboard["description"],
        "permissions": dashboard["permissions"],
        "pages": pages,
    }


def _server_dashboard_projection(dashboard: dict, dashboard_input: dict | None = None) -> dict:
    """Return only fields selected by the current NerdGraph DASHBOARD_GET query."""
    dashboard_input = dashboard_input or _expected_dashboard_input(dashboard, ACCOUNT_ID)
    return {
        "guid": f"dashboard-guid-{dashboard['ownership']}",
        "name": dashboard["name"],
        "accountId": ACCOUNT_ID,
        "description": dashboard["description"],
        "permissions": dashboard["permissions"],
        "variables": [],
        "pages": [
            {
                "guid": f"server-page-{page_index}",
                "name": page["name"],
                "widgets": [
                    {
                        "id": f"server-widget-{page_index}-{widget_index}",
                        "title": rendered_widget["title"],
                        "visualization": deepcopy(rendered_widget["visualization"]),
                        "layout": deepcopy(rendered_widget["layout"]),
                        "linkedEntities": [
                            {"guid": guid}
                            for guid in rendered_widget["linkedEntityGuids"]
                        ],
                        "rawConfiguration": deepcopy(
                            rendered_widget["rawConfiguration"]
                        ),
                    }
                    for widget_index, rendered_widget in enumerate(
                        dashboard_input["pages"][page_index]["widgets"]
                    )
                ],
            }
            for page_index, page in enumerate(dashboard_input["pages"])
        ],
    }


class _NerdGraphLifecycle:
    """Strict stateful NerdGraph fixture for one create/get/apply lifecycle."""

    def __init__(self, dashboard: dict, alerts: dict):
        self.dashboard = dashboard
        self.alerts = alerts
        self.calls: list[tuple[str, dict]] = []
        self.dashboard_guid = f"dashboard-guid-{dashboard['ownership']}"
        self.dashboard_exists = False
        self.dashboard_tagged = False
        self.policy_id = f"policy-id-{dashboard['ownership']}"
        self.policy_exists = False
        self.conditions: dict[str, dict] = {}
        self.get_projection: dict | None = None

    def execute(self, document: str, variables: dict) -> dict:
        variables = deepcopy(dict(variables))
        self.calls.append((document, variables))

        if document == DASHBOARD_SEARCH:
            expected_query = (
                f"accountId = {ACCOUNT_ID} AND type = 'DASHBOARD' "
                f"AND name = '{self.dashboard['name']}'"
            )
            assert variables == {"query": expected_query}
            entities = []
            if self.dashboard_exists:
                entities.append(
                    {
                        "guid": self.dashboard_guid,
                        "name": self.dashboard["name"],
                        "type": "DASHBOARD",
                        "accountId": ACCOUNT_ID,
                        "tags": (
                            [
                                {
                                    "key": "auto-shop.ownership",
                                    "values": [self.dashboard["ownership"]],
                                }
                            ]
                            if self.dashboard_tagged
                            else []
                        ),
                    }
                )
            return {"actor": {"entitySearch": {"results": {"entities": entities}}}}

        if document == DASHBOARD_CREATE:
            assert not self.dashboard_exists
            assert variables["accountId"] == ACCOUNT_ID
            assert variables["dashboard"]["name"] == self.dashboard["name"]
            self.dashboard_exists = True
            self.get_projection = _server_dashboard_projection(
                self.dashboard, variables["dashboard"]
            )
            return {
                "dashboardCreate": {
                    "entityResult": {
                        "guid": self.dashboard_guid,
                        "name": self.dashboard["name"],
                    },
                    "errors": [],
                }
            }

        if document == DASHBOARD_GET:
            assert self.dashboard_exists
            assert variables == {"guid": self.dashboard_guid}
            return {
                "actor": {
                    "entity": {
                        key: deepcopy(value)
                        for key, value in (self.get_projection or {}).items()
                    }
                }
            }

        if document == DASHBOARD_UPDATE:
            assert self.dashboard_exists
            assert variables["guid"] == self.dashboard_guid
            assert variables["dashboard"]["name"] == self.dashboard["name"]
            return {
                "dashboardUpdate": {
                    "entityResult": {
                        "guid": self.dashboard_guid,
                        "name": self.dashboard["name"],
                    },
                    "errors": [],
                }
            }

        if document == TAG_ENTITY:
            assert variables == {
                "guid": self.dashboard_guid,
                "tags": [
                    {
                        "key": "auto-shop.ownership",
                        "values": [self.dashboard["ownership"]],
                    }
                ],
            }
            self.dashboard_tagged = True
            return {"taggingAddTagsToEntity": {"errors": []}}

        if document == POLICY_SEARCH:
            assert variables == {
                "accountId": ACCOUNT_ID,
                "name": self.alerts["policy"]["name"],
            }
            policies = (
                [{"id": self.policy_id, "name": self.alerts["policy"]["name"]}]
                if self.policy_exists
                else []
            )
            return {
                "actor": {
                    "account": {"alerts": {"policiesSearch": {"policies": policies}}}
                }
            }

        if document == POLICY_CREATE:
            assert not self.policy_exists
            assert variables == {
                "accountId": ACCOUNT_ID,
                "policy": {
                    "name": self.alerts["policy"]["name"],
                    "incidentPreference": self.alerts["policy"][
                        "incident_preference"
                    ],
                },
            }
            self.policy_exists = True
            return {
                "alertsPolicyCreate": {
                    "id": self.policy_id,
                    "name": self.alerts["policy"]["name"],
                }
            }

        if document == POLICY_UPDATE:
            assert self.policy_exists
            assert variables == {
                "accountId": ACCOUNT_ID,
                "policyId": self.policy_id,
                "policy": {
                    "name": self.alerts["policy"]["name"],
                    "incidentPreference": self.alerts["policy"][
                        "incident_preference"
                    ],
                },
            }
            return {
                "alertsPolicyUpdate": {
                    "id": self.policy_id,
                    "name": self.alerts["policy"]["name"],
                    "incidentPreference": self.alerts["policy"][
                        "incident_preference"
                    ],
                }
            }

        if document == CONDITION_SEARCH:
            assert self.policy_exists
            assert variables == {"accountId": ACCOUNT_ID, "policyId": self.policy_id}
            conditions = [
                {
                    "id": item["id"],
                    "name": name,
                    "enabled": True,
                    "type": "STATIC",
                }
                for name, item in self.conditions.items()
            ]
            return {
                "actor": {
                    "account": {
                        "alerts": {
                            "nrqlConditionsSearch": {"nrqlConditions": conditions}
                        }
                    }
                }
            }

        if document == CONDITION_GET:
            condition_id = variables["conditionId"]
            condition = next(
                item
                for item in self.conditions.values()
                if item["id"] == condition_id
            )
            return {
                "actor": {
                    "account": {
                        "alerts": {
                            "nrqlCondition": {
                                "id": condition_id,
                                **deepcopy(condition["configuration"]),
                            }
                        }
                    }
                }
            }

        if document in {CONDITION_CREATE, CONDITION_UPDATE}:
            condition_input = variables["condition"]
            expected_condition = next(
                (
                    item
                    for item in self.alerts["conditions"]
                    if item["name"] == condition_input.get("name")
                ),
                None,
            )
            assert expected_condition is not None
            assert condition_input["nrql"] == {"query": expected_condition["nrql"]}
            assert condition_input["enabled"] is True
            assert variables["accountId"] == ACCOUNT_ID
            assert variables.get("policyId", self.policy_id) == self.policy_id
            if document == CONDITION_CREATE:
                assert condition_input["name"] not in self.conditions
                condition_id = f"condition-id-{len(self.conditions) + 1}"
                self.conditions[condition_input["name"]] = {
                    "id": condition_id,
                    "configuration": deepcopy(condition_input),
                }
                result_name = "alertsNrqlConditionStaticCreate"
            else:
                condition_id = variables["conditionId"]
                assert self.conditions[condition_input["name"]]["id"] == condition_id
                self.conditions[condition_input["name"]]["configuration"] = deepcopy(
                    condition_input
                )
                result_name = "alertsNrqlConditionStaticUpdate"
            return {
                result_name: {"id": condition_id, "name": condition_input["name"]}
            }

        if document == CONDITION_DELETE:
            condition_id = variables["conditionId"]
            condition_name = next(
                name
                for name, item in self.conditions.items()
                if item["id"] == condition_id
            )
            del self.conditions[condition_name]
            return {"alertsConditionDelete": {"id": condition_id}}

        raise AssertionError(f"Unexpected NerdGraph document: {document}")


@pytest.mark.parametrize(
    "profile,dashboard_filename,alerts_filename", PROFILE_FILES
)
def test_identical_second_apply_discovers_dashboard_without_updating_it(
    profile: str,
    dashboard_filename: str,
    alerts_filename: str,
):
    dashboard = _load_definition(dashboard_filename)
    alerts = _load_definition(alerts_filename)
    assert dashboard["ownership"] == alerts["ownership"]
    client = _NerdGraphLifecycle(dashboard, alerts)

    first_result = reconcile(
        client, ACCOUNT_ID, dashboard, alerts, action="apply", profile=profile
    )
    first_calls = client.calls.copy()

    assert first_result["dashboard"] == "created"
    assert [document for document, _ in first_calls] == [
        DASHBOARD_SEARCH,
        DASHBOARD_CREATE,
        TAG_ENTITY,
        POLICY_SEARCH,
        POLICY_CREATE,
        CONDITION_SEARCH,
        *([CONDITION_CREATE] * len(alerts["conditions"])),
    ]
    assert first_calls[0][1] == {
        "query": (
            f"accountId = {ACCOUNT_ID} AND type = 'DASHBOARD' "
            f"AND name = '{dashboard['name']}'"
        )
    }
    assert first_calls[1][1]["accountId"] == ACCOUNT_ID
    assert first_calls[1][1]["dashboard"]["name"] == dashboard["name"]
    assert first_calls[2][1]["guid"] == client.dashboard_guid
    assert first_calls[4][1] == {
        "accountId": ACCOUNT_ID,
        "policy": {
            "name": alerts["policy"]["name"],
            "incidentPreference": alerts["policy"]["incident_preference"],
        },
    }

    created_conditions = [
        variables
        for document, variables in first_calls
        if document == CONDITION_CREATE
    ]
    assert [item["condition"]["name"] for item in created_conditions] == [
        item["name"] for item in alerts["conditions"]
    ]
    assert [item["condition"]["nrql"]["query"] for item in created_conditions] == [
        item["nrql"] for item in alerts["conditions"]
    ]
    assert all(item["accountId"] == ACCOUNT_ID for item in created_conditions)
    assert all(item["policyId"] == client.policy_id for item in created_conditions)

    second_result = reconcile(
        client, ACCOUNT_ID, dashboard, alerts, action="apply", profile=profile
    )
    second_calls = client.calls[len(first_calls) :]
    second_documents = [document for document, _ in second_calls]

    assert second_documents[:2] == [DASHBOARD_SEARCH, DASHBOARD_GET]
    assert second_calls[1][1] == {"guid": client.dashboard_guid}
    assert DASHBOARD_UPDATE not in second_documents
    assert second_result["dashboard"] == "unchanged", profile
    assert DASHBOARD_CREATE not in second_documents
    assert TAG_ENTITY not in second_documents
    assert POLICY_CREATE not in second_documents
    assert CONDITION_CREATE not in second_documents
    assert CONDITION_UPDATE not in second_documents
    assert len(client.conditions) == len(alerts["conditions"])
    assert len({item["id"] for item in client.conditions.values()}) == len(
        alerts["conditions"]
    )


@pytest.mark.parametrize(
    "profile,dashboard_filename,alerts_filename", PROFILE_FILES
)
def test_update_rendering_preserves_server_page_and_widget_ids(
    profile: str,
    dashboard_filename: str,
    alerts_filename: str,
):
    dashboard = _load_definition(dashboard_filename)
    alerts = _load_definition(alerts_filename)
    assert dashboard["ownership"] == alerts["ownership"]
    existing = _server_dashboard_projection(dashboard)

    get_document = " ".join(DASHBOARD_GET.split())
    for selected_field in (
        "guid name accountId description permissions",
        "pages {",
        "guid name description",
        "visualization { id }",
        "layout { row column height width }",
        "linkedEntities { guid }",
        "rawConfiguration",
        "variables {",
    ):
        assert selected_field in get_document
    rendered = _dashboard_input(dashboard, ACCOUNT_ID, existing)

    assert [page["guid"] for page in rendered["pages"]] == [
        page["guid"] for page in existing["pages"]
    ]
    for page_index, (expected_page, rendered_page) in enumerate(
        zip(dashboard["pages"], rendered["pages"], strict=True)
    ):
        expected_ids = {
            widget["title"]: widget["id"]
            for widget in existing["pages"][page_index]["widgets"]
        }
        rendered_ids = {widget["title"]: widget["id"] for widget in rendered_page["widgets"]}
        assert rendered_ids == expected_ids, profile
        assert [
            widget["rawConfiguration"]["nrqlQueries"][0]["query"]
            for widget in rendered_page["widgets"]
        ] == [widget["nrql"] for widget in expected_page["widgets"]]


def test_service_order_apply_replaces_owned_drifted_legacy_condition():
    dashboard = _load_definition("service-order-dashboard.json")
    alerts = _load_definition("service-order-alerts.json")
    client = _NerdGraphLifecycle(dashboard, alerts)

    reconcile(
        client,
        ACCOUNT_ID,
        dashboard,
        alerts,
        action="apply",
        profile="service-order",
    )
    condition_name = alerts["conditions"][0]["name"]
    client.conditions[condition_name]["configuration"]["description"] = (
        "Legacy condition requiring migration"
    )
    call_count = len(client.calls)

    result = reconcile(
        client,
        ACCOUNT_ID,
        dashboard,
        alerts,
        action="apply",
        profile="service-order",
    )
    documents = [document for document, _ in client.calls[call_count:]]

    assert CONDITION_GET in documents
    assert CONDITION_DELETE in documents
    assert CONDITION_CREATE in documents
    assert CONDITION_UPDATE not in documents
    assert result["conditions"] == 1
    assert client.conditions[condition_name]["configuration"]["description"] == (
        "Owned aggregate HML condition: service_order_failure"
    )

