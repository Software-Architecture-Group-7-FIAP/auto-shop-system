#!/usr/bin/env python3
"""Allow only narrowly scoped API Gateway/ALB edge lifecycle changes."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ALB_RULE_PREFIXES = (
    "aws_vpc_security_group_egress_rule.vpc_link_to_alb[",
    "aws_vpc_security_group_ingress_rule.alb_from_vpc_link[",
)
API_INTEGRATIONS = {
    "aws_api_gateway_integration.api_v1_auth_http",
    "aws_api_gateway_integration.auth_login_lambda",
    "aws_api_gateway_integration.auth_login_options_http",
    "aws_api_gateway_integration.admin_http",
    "aws_api_gateway_integration.admin_options_http",
    "aws_api_gateway_integration.public_http",
    "aws_api_gateway_integration.customer_http",
    "aws_api_gateway_integration.health_http",
}


def _read_plan(plan_path: Path) -> dict[str, Any]:
    result = subprocess.run(
        ["terraform", "show", "-json", str(plan_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    decoded = json.loads(result.stdout)
    if not isinstance(decoded, dict) or not isinstance(decoded.get("resource_changes"), list):
        raise ValueError("Terraform plan JSON did not contain resource_changes.")
    return decoded


def _is_allowed(mode: str, address: str, actions: list[str]) -> bool:
    if any(address.startswith(prefix) for prefix in ALB_RULE_PREFIXES):
        if mode == "maintenance":
            return actions == ["delete"]
        return actions in (["create"], ["update"], ["delete"])
    if mode == "active" and address in API_INTEGRATIONS:
        return actions == ["update"]
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("active", "maintenance"), required=True)
    parser.add_argument("--plan", type=Path, required=True)
    arguments = parser.parse_args()

    try:
        plan = _read_plan(arguments.plan)
    except (OSError, subprocess.CalledProcessError, json.JSONDecodeError, ValueError):
        print("::error::Could not inspect the Terraform plan; edge changes were blocked.", file=sys.stderr)
        return 1

    changes: list[tuple[str, list[str]]] = []
    for item in plan["resource_changes"]:
        change = item.get("change") or {}
        actions = change.get("actions")
        if actions == ["no-op"] or actions == ["read"]:
            continue
        address = str(item.get("address", ""))
        if not isinstance(actions, list) or not _is_allowed(arguments.mode, address, actions):
            print(
                f"::error::Terraform plan contains a change outside the {arguments.mode} edge allowlist: {address} {actions}.",
                file=sys.stderr,
            )
            return 1
        changes.append((address, actions))

    if arguments.mode == "maintenance" and any(actions != ["delete"] for _, actions in changes):
        print("::error::Maintenance may only remove ALB security-group reference rules.", file=sys.stderr)
        return 1
    if any(address in API_INTEGRATIONS for address, actions in changes if actions != ["update"]):
        print("::error::Active edge reconciliation may update integrations but cannot replace or delete them.", file=sys.stderr)
        return 1

    print(f"Terraform plan passed the {arguments.mode} edge change allowlist ({len(changes)} changes).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
