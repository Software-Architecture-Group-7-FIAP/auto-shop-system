"""Bounded, sanitized HTTP client and GraphQL documents for New Relic NerdGraph."""

from __future__ import annotations

import json
import re
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
_GRAPHQL_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")
_OPERATION_NAME = re.compile(r"^\s*(?:query|mutation|subscription)\s+([A-Za-z_][A-Za-z0-9_]*)\b")
_GRAPHQL_ERROR_CATEGORIES = (
    (
        "authorization",
        (
            "unauthorized",
            "unauthorised",
            "not authorized",
            "not authorised",
            "forbidden",
            "permission denied",
            "access denied",
            "insufficient permission",
            "insufficient privilege",
        ),
    ),
    (
        "not-found",
        ("not found", "does not exist", "doesn't exist", "could not find", "no such "),
    ),
    (
        "validation",
        (
            "invalid",
            "validation",
            "bad input",
            "unknown argument",
            "not defined by type",
            "cannot query field",
            "required",
            "must be provided",
            "unsupported",
            "limit exceeded",
        ),
    ),
)
_GRAPHQL_ERROR_CODES = frozenset(
    {
        "BAD_USER_INPUT",
        "FORBIDDEN",
        "GRAPHQL_VALIDATION_FAILED",
        "INTERNAL_SERVER_ERROR",
        "NOT_FOUND",
        "RESOURCE_NOT_FOUND",
        "UNAUTHENTICATED",
        "UNAUTHORIZED",
        "VALIDATION_ERROR",
    }
)
_GRAPHQL_ERROR_TYPES = frozenset(
    {
        "ACCESS_DENIED",
        "AUTHENTICATION_ERROR",
        "INTERNAL_SERVER_ERROR",
        "NOT_FOUND",
        "PERMISSION_DENIED",
        "RESOURCE_NOT_FOUND",
        "VALIDATION_ERROR",
    }
)
_GRAPHQL_DIAGNOSTIC_PATTERNS = (
    (
        re.compile(
            r"Field\s+['\"]([A-Za-z_][A-Za-z0-9_]*)['\"]\s+is not defined by type\s+['\"]([A-Za-z_][A-Za-z0-9_]*)['\"]",
            re.IGNORECASE,
        ),
        "input field '{0}' is not defined on '{1}'",
    ),
    (
        re.compile(
            r"Cannot query field\s+['\"]([A-Za-z_][A-Za-z0-9_]*)['\"]\s+on type\s+['\"]([A-Za-z_][A-Za-z0-9_]*)['\"]",
            re.IGNORECASE,
        ),
        "selected field '{0}' is not defined on '{1}'",
    ),
    (
        re.compile(
            r"Unknown argument\s+['\"]([A-Za-z_][A-Za-z0-9_]*)['\"]\s+on field\s+['\"]([A-Za-z_][A-Za-z0-9_.]*)['\"]",
            re.IGNORECASE,
        ),
        "argument '{0}' is not defined on field '{1}'",
    ),
    (
        re.compile(
            r"Field\s+['\"]([A-Za-z_][A-Za-z0-9_]*)['\"]\s+of required type\s+['\"]([A-Za-z_][A-Za-z0-9_!\[\]]*)['\"]\s+was not provided",
            re.IGNORECASE,
        ),
        "required input field '{0}' of type '{1}' is missing",
    ),
)


def _graphql_operation_name(document: str) -> str | None:
    match = _OPERATION_NAME.match(document)
    if match is None:
        return None
    return match.group(1)


def _graphql_error_path(error: Mapping[str, object]) -> str | None:
    path = error.get("path")
    if not isinstance(path, list) or not 1 <= len(path) <= 20:
        return None
    segments = []
    for segment in path:
        if isinstance(segment, str) and _GRAPHQL_IDENTIFIER.fullmatch(segment):
            segments.append(segment)
        elif isinstance(segment, int) and not isinstance(segment, bool) and 0 <= segment <= 9_999:
            segments.append(f"[{segment}]")
        else:
            return None
    return ".".join(segments).replace(".[", "[")


def _graphql_message_category(message: object) -> str | None:
    if not isinstance(message, str):
        return None
    normalized = message.casefold()
    return next(
        (
            category
            for category, markers in _GRAPHQL_ERROR_CATEGORIES
            if any(marker in normalized for marker in markers)
        ),
        None,
    )


def _allowlisted_graphql_identifier(value: object, allowed: frozenset[str]) -> str | None:
    if not isinstance(value, str):
        return None
    identifier = value.upper()
    return identifier if identifier in allowed else None


def _graphql_error_detail(errors: object, document: str) -> str:
    if not isinstance(errors, list):
        return " (GraphQL details redacted)"

    details = []
    for error in errors[:3]:
        if not isinstance(error, Mapping):
            continue
        message = error.get("message")
        error_details = []
        category = _graphql_message_category(message)
        if category:
            error_details.append(f"category={category}")
        if isinstance(message, str):
            for pattern, template in _GRAPHQL_DIAGNOSTIC_PATTERNS:
                match = pattern.search(message)
                if match:
                    error_details.append(template.format(*match.groups()))
                    break

        extensions = error.get("extensions")
        if isinstance(extensions, Mapping):
            code = _allowlisted_graphql_identifier(
                extensions.get("code"), _GRAPHQL_ERROR_CODES
            )
            error_type = _allowlisted_graphql_identifier(
                extensions.get("errorType"), _GRAPHQL_ERROR_TYPES
            )
            if code:
                error_details.append(f"code={code}")
            if error_type:
                error_details.append(f"errorType={error_type}")

        path = _graphql_error_path(error)
        if path:
            error_details.append(f"path: {path}")
        if error_details:
            details.append("; ".join(error_details))

    if not details:
        details.append("GraphQL details redacted")
    operation_name = _graphql_operation_name(document)
    prefix = f"{operation_name}: " if operation_name else ""
    return f" ({prefix}{'; '.join(details[:3])})"

DASHBOARD_SEARCH = """
query OwnedDashboard($query: String!) {
  actor { entitySearch(query: $query) { results { entities { guid name type accountId tags { key values } } } } }
}
"""
DASHBOARD_GET = """
query OwnedDashboardStructure($guid: EntityGuid!) {
  actor { entity(guid: $guid) { ... on DashboardEntity {
    guid name accountId description permissions
    pages {
      guid name description
      widgets {
        id title visualization { id } layout { row column height width }
        linkedEntities { guid }
        rawConfiguration
      }
    }
    variables {
      name title type nrqlQuery { accountIds query }
      defaultValues { value { string } }
      options { excluded ignoreTimeRange showApplyAction hiddenOnVariablesBar }
      isMultiSelection replacementStrategy
    }
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
        if not isinstance(payload, dict):
            raise ProvisioningError("NerdGraph returned an invalid response")
        errors = payload.get("errors")
        if errors:
            detail = _graphql_error_detail(errors, document)
            raise ProvisioningError(f"NerdGraph rejected the operation{detail}") from None
        data = payload.get("data")
        if not isinstance(data, dict):
            raise ProvisioningError("NerdGraph response did not contain operation data")
        return data
