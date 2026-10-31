#!/usr/bin/env python3
"""Fail closed unless this workflow run was triggered by a trusted lifecycle actor."""

import argparse
import os
import re
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require-dispatch-actor", action="store_true")
    parser.add_argument("--dispatch-only", action="store_true")
    arguments = parser.parse_args()

    if arguments.require_dispatch_actor and arguments.dispatch_only:
        parser.error("--require-dispatch-actor and --dispatch-only cannot be combined")

    actor = os.environ.get("GITHUB_ACTOR", "")
    triggering_actor = os.environ.get("LIFECYCLE_TRIGGERING_ACTOR", "")
    dispatch_actor = os.environ.get("LIFECYCLE_CROSS_REPO_ACTOR", "")
    actor_pattern = re.compile(r"^[A-Za-z0-9-]{1,39}(?:\[bot\])?$")
    allowlist = {
        entry.strip()
        for entry in os.environ.get("LIFECYCLE_TRUSTED_OPERATORS", "").split(",")
        if entry.strip()
    }
    if not triggering_actor or triggering_actor != actor:
        print(
            "::error::The triggering actor does not match the original workflow actor; lifecycle authorization fails closed.",
            file=sys.stderr,
        )
        return 1
    if not allowlist:
        print("::error::LIFECYCLE_TRUSTED_OPERATORS must contain at least one exact actor.", file=sys.stderr)
        return 1
    if not arguments.dispatch_only and (
        not actor_pattern.fullmatch(actor) or actor not in allowlist
    ):
        print(
            "::error::The GitHub actor is not in the exact LIFECYCLE_TRUSTED_OPERATORS allowlist.",
            file=sys.stderr,
        )
        return 1
    if arguments.require_dispatch_actor or arguments.dispatch_only:
        if not actor_pattern.fullmatch(dispatch_actor) or dispatch_actor not in allowlist:
            print(
                "::error::LIFECYCLE_CROSS_REPO_ACTOR must be a valid actor in LIFECYCLE_TRUSTED_OPERATORS.",
                file=sys.stderr,
            )
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
