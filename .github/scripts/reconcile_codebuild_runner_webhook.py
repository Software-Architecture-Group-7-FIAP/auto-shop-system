#!/usr/bin/env python3
"""Safely align the HML CodeBuild runner webhook with deployment run names."""

from __future__ import annotations

import argparse
import copy
import json
import re
import subprocess
import sys
from collections.abc import Sequence
from typing import Any

PROJECT_NAME = "auto-shop-hml-private-runner"
DEFAULT_REGION = "us-east-1"
EXPECTED_REPOSITORY = "Software-Architecture-Group-7-FIAP/auto-shop-system"
DYNAMIC_WEBHOOK_SOURCE_LOCATION = "CODEBUILD_DEFAULT_WEBHOOK_SOURCE_LOCATION"
LEGACY_WORKFLOW_NAME_PATTERN = r"^HML deploy [0-9a-f]{40}$"
TARGET_WORKFLOW_NAME_PATTERN = (
    r"^(HML deploy [0-9a-f]{40}|lifecycle:(hml|prd)-[0-9]{4}-[0-9]{2}-[0-9]{2}:"
    r"app-deploy:([0-9a-f]{32}|[1-9][0-9]{0,19}))$"
)
ACCOUNT_ID_PATTERN = re.compile(r"^[0-9]{12}$")
RUNNER_EVENT = "WORKFLOW_JOB_QUEUED"


class WebhookContractError(ValueError):
    """Raised when the current webhook differs from the reviewed contract."""


def reconcile_filter_groups(
    filter_groups: Sequence[Sequence[dict[str, Any]]],
) -> tuple[list[list[dict[str, Any]]], bool]:
    """Replace only the runner event's known workflow-name filter."""
    if not isinstance(filter_groups, (list, tuple)) or not filter_groups:
        raise WebhookContractError("The CodeBuild webhook has no filter groups.")
    if any(
        not isinstance(group, (list, tuple))
        or any(not isinstance(item, dict) for item in group)
        for group in filter_groups
    ):
        raise WebhookContractError("The CodeBuild webhook filters have an unexpected shape.")

    runner_group_indexes = []
    for index, group in enumerate(filter_groups):
        event_filters = [item for item in group if item.get("type") == "EVENT"]
        if any(item.get("pattern") == RUNNER_EVENT for item in event_filters):
            runner_group_indexes.append(index)
            if (
                len(event_filters) != 1
                or event_filters[0].get("pattern") != RUNNER_EVENT
                or event_filters[0].get("excludeMatchedPattern", False)
            ):
                raise WebhookContractError(
                    "The runner event group must positively match only WORKFLOW_JOB_QUEUED."
                )
    if len(runner_group_indexes) != 1:
        raise WebhookContractError(
            "Expected exactly one WORKFLOW_JOB_QUEUED filter group."
        )

    updated = copy.deepcopy(list(filter_groups))
    group_index = runner_group_indexes[0]
    runner_group = updated[group_index]
    workflow_filter_indexes = [
        index
        for index, item in enumerate(runner_group)
        if item.get("type") == "WORKFLOW_NAME"
    ]
    if len(workflow_filter_indexes) != 1:
        raise WebhookContractError(
            "Expected exactly one WORKFLOW_NAME filter in the runner event group."
        )

    workflow_filter = runner_group[workflow_filter_indexes[0]]
    current_pattern = workflow_filter.get("pattern")
    if workflow_filter.get("excludeMatchedPattern", False):
        raise WebhookContractError(
            "The runner WORKFLOW_NAME filter must positively match its pattern."
        )
    if current_pattern == TARGET_WORKFLOW_NAME_PATTERN:
        return updated, False
    if current_pattern != LEGACY_WORKFLOW_NAME_PATTERN:
        raise WebhookContractError(
            "The runner WORKFLOW_NAME filter is not the reviewed legacy or target pattern; "
            "inspect the webhook before updating it."
        )

    workflow_filter["pattern"] = TARGET_WORKFLOW_NAME_PATTERN
    return updated, True


def _run_aws_json(
    arguments: Sequence[str], *, region: str, profile: str | None
) -> dict[str, Any]:
    command = ["aws"]
    if profile:
        command.extend(["--profile", profile])
    command.extend(
        [*arguments, "--region", region, "--output", "json", "--no-cli-pager"]
    )
    try:
        result = subprocess.run(
            command, check=False, capture_output=True, text=True, timeout=30
        )
    except subprocess.TimeoutExpired as error:
        command_name = " ".join(arguments[:2])
        raise WebhookContractError(f"{command_name} timed out.") from error
    if result.returncode != 0:
        command_name = " ".join(arguments[:2])
        detail = result.stderr.strip() or "AWS CLI returned a non-zero exit status."
        raise WebhookContractError(f"{command_name} failed: {detail}")
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise WebhookContractError("AWS CLI returned invalid JSON.") from error
    if not isinstance(value, dict):
        raise WebhookContractError("AWS CLI returned an unexpected response shape.")
    return value


def _normalized_repository_location(location: str) -> str:
    normalized = location.strip().rstrip("/")
    normalized = normalized.removesuffix(".git")
    for prefix in (
        "https://github.com/",
        "git@github.com:",
        "ssh://git@github.com/",
    ):
        if normalized.startswith(prefix):
            return normalized[len(prefix) :]
    return ""


def _get_project(*, region: str, profile: str | None) -> dict[str, Any]:
    response = _run_aws_json(
        ["codebuild", "batch-get-projects", "--names", PROJECT_NAME],
        region=region,
        profile=profile,
    )
    projects = response.get("projects")
    if not isinstance(projects, list) or len(projects) != 1:
        raise WebhookContractError(
            f"CodeBuild project {PROJECT_NAME} was not found exactly once."
        )

    project = projects[0]
    if not isinstance(project, dict):
        raise WebhookContractError("CodeBuild returned an unexpected project shape.")
    if project.get("name") != PROJECT_NAME:
        raise WebhookContractError("CodeBuild returned an unexpected project.")
    source = project.get("source", {})
    if not isinstance(source, dict) or source.get("type") != "GITHUB":
        raise WebhookContractError("The runner project source is not GitHub.")
    source_location = str(source.get("location", ""))
    if (
        source_location != DYNAMIC_WEBHOOK_SOURCE_LOCATION
        and _normalized_repository_location(source_location) != EXPECTED_REPOSITORY
    ):
        raise WebhookContractError(
            "The runner project is not connected to the expected repository."
        )
    webhook = project.get("webhook")
    if not isinstance(webhook, dict) or webhook.get("status") != "ACTIVE":
        raise WebhookContractError("The runner project has no active webhook configuration.")
    return project


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--expected-account-id",
        required=True,
        help="12-digit AWS account ID to guard the read and optional update.",
    )
    parser.add_argument("--region", default=DEFAULT_REGION)
    parser.add_argument("--profile", help="AWS CLI profile; credentials stay in AWS config.")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply the reviewed filter change. Without this flag, the command is read-only.",
    )
    args = parser.parse_args(argv)
    if not ACCOUNT_ID_PATTERN.fullmatch(args.expected_account_id):
        parser.error("--expected-account-id must contain exactly 12 digits.")
    if not args.region.strip():
        parser.error("--region must not be empty.")
    return args


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        identity = _run_aws_json(
            ["sts", "get-caller-identity"], region=args.region, profile=args.profile
        )
        actual_account_id = identity.get("Account")
        if actual_account_id != args.expected_account_id:
            raise WebhookContractError(
                "The active AWS identity does not match --expected-account-id."
            )

        project = _get_project(region=args.region, profile=args.profile)
        current_groups = project["webhook"].get("filterGroups")
        if not isinstance(current_groups, list):
            raise WebhookContractError("The runner webhook has no filter groups.")
        updated_groups, changed = reconcile_filter_groups(current_groups)
        if not changed:
            print(f"{PROJECT_NAME} already matches the reviewed webhook contract.")
            return 0

        if not args.apply:
            print(
                f"Read-only plan: update {PROJECT_NAME} WORKFLOW_NAME from "
                f"{LEGACY_WORKFLOW_NAME_PATTERN} to {TARGET_WORKFLOW_NAME_PATTERN}; "
                "pass --apply to make this change."
            )
            return 0

        _run_aws_json(
            [
                "codebuild",
                "update-webhook",
                "--project-name",
                PROJECT_NAME,
                "--filter-groups",
                json.dumps(updated_groups, separators=(",", ":")),
            ],
            region=args.region,
            profile=args.profile,
        )

        verified_project = _get_project(region=args.region, profile=args.profile)
        verified_groups = verified_project["webhook"].get("filterGroups")
        if verified_groups != updated_groups:
            raise WebhookContractError(
                "CodeBuild did not return the requested webhook filter groups after update."
            )
        print(f"{PROJECT_NAME} webhook now matches the reviewed workflow-name contract.")
        return 0
    except WebhookContractError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
