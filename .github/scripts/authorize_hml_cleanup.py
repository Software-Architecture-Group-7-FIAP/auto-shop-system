#!/usr/bin/env python3
"""Authorize HML emergency cleanup dispatches before lifecycle credentials are used."""

from __future__ import annotations

import os
import re
import sys


GITHUB_LOGIN = re.compile(r"^[A-Za-z0-9-]{1,39}$")


class CleanupAuthorizationError(ValueError):
    """Raised when a manual HML cleanup actor is not explicitly trusted."""


def authorize_cleanup(*, event_name: str, actor: str, trusted_operators: str) -> bool:
    if event_name == "schedule":
        return True
    if event_name != "workflow_dispatch":
        raise CleanupAuthorizationError("HML emergency cleanup only supports schedule and workflow_dispatch events")
    if not GITHUB_LOGIN.fullmatch(actor.strip()):
        raise CleanupAuthorizationError("A valid GitHub actor is required for manual HML cleanup")

    raw_operators = trusted_operators.split(",")
    operators = [operator.strip() for operator in raw_operators if operator.strip()]
    if not operators:
        raise CleanupAuthorizationError("HML_CLEANUP_TRUSTED_OPERATORS must be configured for manual cleanup")
    if any(not GITHUB_LOGIN.fullmatch(operator) for operator in operators):
        raise CleanupAuthorizationError("HML_CLEANUP_TRUSTED_OPERATORS contains an invalid GitHub login")
    if actor.casefold() not in {operator.casefold() for operator in operators}:
        raise CleanupAuthorizationError("The manual HML cleanup actor is not in the trusted operator list")
    return True


def main() -> int:
    try:
        authorize_cleanup(
            event_name=os.environ.get("REQUESTED_EVENT_NAME", "").strip(),
            actor=os.environ.get("REQUESTED_ACTOR", "").strip(),
            trusted_operators=os.environ.get("HML_CLEANUP_TRUSTED_OPERATORS", ""),
        )
    except CleanupAuthorizationError as error:
        print(f"::error::{error}", file=sys.stderr)
        return 1
    print("HML emergency cleanup trigger is authorized.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
