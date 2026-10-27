"""Generate or check the versioned OpenAPI document for the FastAPI app."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OPENAPI_PATH = PROJECT_ROOT / "docs" / "api" / "openapi.json"


def render_openapi() -> str:
    """Return a stable JSON representation of the application schema."""
    project_root = str(PROJECT_ROOT)
    if not sys.path or sys.path[0] != project_root:
        sys.path.insert(0, project_root)

    from src.main import app

    return json.dumps(app.openapi(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail if the committed OpenAPI document differs from the application",
    )
    args = parser.parse_args(argv)
    expected = render_openapi()

    if args.check:
        if not OPENAPI_PATH.is_file():
            print(
                f"{OPENAPI_PATH.relative_to(PROJECT_ROOT)} is missing; generate it with "
                "`poetry run python scripts/export_openapi.py`.",
                file=sys.stderr,
            )
            return 1

        actual = OPENAPI_PATH.read_text(encoding="utf-8")
        if actual != expected:
            print(
                "The versioned OpenAPI document is out of date; run "
                "`poetry run python scripts/export_openapi.py` and commit the result.",
                file=sys.stderr,
            )
            return 1

        print("The versioned OpenAPI document matches the FastAPI application.")
        return 0

    OPENAPI_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OPENAPI_PATH.open("w", encoding="utf-8", newline="\n") as openapi_file:
        openapi_file.write(expected)
    print(f"Generated {OPENAPI_PATH.relative_to(PROJECT_ROOT)}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
