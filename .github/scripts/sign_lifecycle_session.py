#!/usr/bin/env python3
"""Write a signed lifecycle session capability to GITHUB_ENV only."""

from __future__ import annotations

import argparse
import os
import sys

from lifecycle_session_auth import (
    LifecycleSessionAuthError,
    sign_emergency_hml_cleanup,
    sign_lifecycle_session,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--emergency-hml-cleanup", action="store_true")
    arguments = parser.parse_args()

    environment_file = os.environ.get("GITHUB_ENV", "")
    if not environment_file:
        print("::error::GITHUB_ENV is required to store the lifecycle session capability.", file=sys.stderr)
        return 1

    try:
        signing_key = os.environ.get("LIFECYCLE_SESSION_SIGNING_KEY", "")
        session_mode = os.environ.get("SESSION_MODE", "")
        session_id = os.environ.get("SESSION_ID", "")
        started_at = os.environ.get("STARTED_AT", "")
        if arguments.emergency_hml_cleanup:
            if session_mode != "hml":
                raise LifecycleSessionAuthError("Emergency cleanup capabilities are available only for HML.")
            token = sign_emergency_hml_cleanup(
                signing_key,
                session_id,
                started_at,
                os.environ.get("CLOSE_REQUEST_ID", ""),
            )
        else:
            token = sign_lifecycle_session(signing_key, session_mode, session_id, started_at)
        with open(environment_file, "a", encoding="utf-8") as output:
            output.write(f"LIFECYCLE_SESSION_TOKEN={token}\n")
    except (LifecycleSessionAuthError, OSError) as error:
        print(f"::error::Lifecycle session signing failed closed: {error}", file=sys.stderr)
        return 1

    print("Lifecycle session capability prepared for authenticated dispatch.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
