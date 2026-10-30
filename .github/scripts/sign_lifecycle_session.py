#!/usr/bin/env python3
"""Write a signed lifecycle session capability to GITHUB_ENV only."""

from __future__ import annotations

import os
import sys

from lifecycle_session_auth import LifecycleSessionAuthError, sign_lifecycle_session


def main() -> int:
    environment_file = os.environ.get("GITHUB_ENV", "")
    if not environment_file:
        print("::error::GITHUB_ENV is required to store the lifecycle session capability.", file=sys.stderr)
        return 1

    try:
        token = sign_lifecycle_session(
            os.environ.get("LIFECYCLE_SESSION_SIGNING_KEY", ""),
            os.environ.get("SESSION_MODE", ""),
            os.environ.get("SESSION_ID", ""),
            os.environ.get("STARTED_AT", ""),
        )
        with open(environment_file, "a", encoding="utf-8") as output:
            output.write(f"LIFECYCLE_SESSION_TOKEN={token}\n")
    except (LifecycleSessionAuthError, OSError) as error:
        print(f"::error::Lifecycle session signing failed closed: {error}", file=sys.stderr)
        return 1

    print("Lifecycle session capability prepared for authenticated dispatch.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
