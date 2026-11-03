"""Bounded, sanitized HTTP client and GraphQL documents for New Relic NerdGraph."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener


ENDPOINTS = {
    "us": "https://api.newrelic.com/graphql",
    "eu": "https://api.eu.newrelic.com/graphql",
}
REQUEST_TIMEOUT_SECONDS = 10
MAX_RESPONSE_BYTES = 1_048_576

DASHBOARD_SEARCH = """
query OwnedDashboard($query: String!) {
  actor { entitySearch(query: $query) { results { entities { guid name type accountId tags { key values } } } } }
}
"""
DASHBOARD_GET = """
query OwnedDashboardStructure($guid: EntityGuid!) {
  actor { entity(guid: $guid) { ... on DashboardEntity {
    guid name accountId pages { guid name widgets { id title } }
  } } }
}
"""
DASHBOARD_CREATE = """
mutation CreateDashboard($accountId: Int!, $dashboard: DashboardInput!) {
  dashboardCreate(accountId: $accountId, dashboard: $dashboard) {
    entityResult { guid name }
    errors { type }
  }
}
"""
DASHBOARD_UPDATE = """
mutation UpdateDashboard($guid: EntityGuid!, $dashboard: DashboardUpdateInput!) {
  dashboardUpdate(guid: $guid, dashboard: $dashboard) {
    entityResult { guid name }
    errors { type }
  }
}
"""
TAG_ENTITY = """
mutation TagOwnedEntity($guid: EntityGuid!, $tags: [TaggingTagInput!]!) {
  taggingAddTagsToEntity(guid: $guid, tags: $tags) { errors { type } }
}
"""
POLICY_SEARCH = """
query OwnedPolicy($accountId: Int!, $name: String!) {
  actor { account(id: $accountId) { alerts {
    policiesSearch(searchCriteria: {name: $name}) { policies { id name } }
  } } }
}
"""
POLICY_CREATE = """
mutation CreatePolicy($accountId: Int!, $policy: AlertsPolicyInput!) {
  alertsPolicyCreate(accountId: $accountId, policy: $policy) { id name }
}
"""
POLICY_UPDATE = """
mutation UpdatePolicy($accountId: Int!, $policyId: ID!, $policy: AlertsPolicyUpdateInput!) {
  alertsPolicyUpdate(accountId: $accountId, id: $policyId, policy: $policy) { id name incidentPreference }
}
"""
CONDITION_SEARCH = """
query OwnedConditions($accountId: Int!, $policyId: ID!) {
  actor { account(id: $accountId) { alerts {
    nrqlConditionsSearch(searchCriteria: {policyId: $policyId}) {
      nrqlConditions { id name enabled type }
    }
  } } }
}
"""
CONDITION_CREATE = """
mutation CreateCondition($accountId: Int!, $policyId: ID!, $condition: AlertsNrqlConditionStaticInput!) {
  alertsNrqlConditionStaticCreate(accountId: $accountId, policyId: $policyId, condition: $condition) { id name }
}
"""
CONDITION_UPDATE = """
mutation UpdateCondition($accountId: Int!, $conditionId: ID!, $condition: AlertsNrqlConditionStaticInput!) {
  alertsNrqlConditionStaticUpdate(accountId: $accountId, id: $conditionId, condition: $condition) { id name }
}
"""


class ProvisioningError(RuntimeError):
    """A sanitized, user-facing provisioning failure."""


class _RejectRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        return None


class NerdGraphClient:
    def __init__(
        self,
        *,
        api_key: str,
        region: str,
        opener: Callable[..., object] | None = None,
    ) -> None:
        if region not in ENDPOINTS:
            raise ValueError("New Relic region must be us or eu")
        if not api_key or not all(0x21 <= ord(character) <= 0x7E for character in api_key):
            raise ValueError("A printable New Relic User API key is required")
        self._api_key = api_key
        self._endpoint = ENDPOINTS[region]
        self._opener = opener or build_opener(_RejectRedirectHandler()).open

    def execute(self, document: str, variables: Mapping[str, object]) -> dict[str, Any]:
        body = json.dumps(
            {"query": document, "variables": dict(variables)},
            separators=(",", ":"),
        ).encode("utf-8")
        request = Request(
            self._endpoint,
            data=body,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Api-Key": self._api_key,
            },
            method="POST",
        )
        try:
            with self._opener(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
        except HTTPError as error:
            error.close()
            raise ProvisioningError("NerdGraph returned a non-success HTTP status") from None
        except (URLError, TimeoutError, OSError):
            raise ProvisioningError("NerdGraph request could not be completed") from None
        if len(raw) > MAX_RESPONSE_BYTES:
            raise ProvisioningError("NerdGraph response exceeded the fixed size limit")
        try:
            payload = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ProvisioningError("NerdGraph returned an invalid response") from None
        if not isinstance(payload, dict) or payload.get("errors"):
            raise ProvisioningError("NerdGraph rejected the operation")
        data = payload.get("data")
        if not isinstance(data, dict):
            raise ProvisioningError("NerdGraph response did not contain operation data")
        return data
