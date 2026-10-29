"""Render the versioned Mermaid sources as SVG and PNG artifacts."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DIAGRAM_DIR = PROJECT_ROOT / "docs" / "architecture" / "diagrams"
DATABASE_SCHEMA = PROJECT_ROOT / "docs" / "database" / "database-schema.mermaid"
AWS_ICON_PACK = DIAGRAM_DIR / "aws-icons.json"
MERMAID_CLI_VERSION = "12.0.0"


def main() -> int:
    """Render phase 3, UML, and ER diagrams."""
    sources = [(path, path.stem) for path in sorted(DIAGRAM_DIR.glob("*.mmd"))]
    sources.append((DATABASE_SCHEMA, "database-er"))

    for source, artifact_name in sources:
        if not source.is_file():
            raise FileNotFoundError(f"Mermaid source not found: {source}")

        for extension in ("svg", "png"):
            output = DIAGRAM_DIR / f"{artifact_name}.{extension}"
            arguments = [
                "--yes",
                "--package",
                f"@mermaid-js/mermaid-cli@{MERMAID_CLI_VERSION}",
                "mmdc",
                "--input",
                str(source),
                "--output",
                str(output),
                "--backgroundColor",
                "white",
            ]
            if source.name == "componentes-fase-3.mmd":
                if not AWS_ICON_PACK.is_file():
                    raise FileNotFoundError(f"AWS icon pack not found: {AWS_ICON_PACK}")
                arguments.extend(
                    [
                        "--iconPacksNamesAndUrls",
                        f"aws#{AWS_ICON_PACK.as_uri()}",
                    ]
                )

            command = (
                ["cmd.exe", "/d", "/c", "npx", *arguments]
                if os.name == "nt"
                else ["npx", *arguments]
            )
            print(
                f"Rendering {source.relative_to(PROJECT_ROOT)} "
                f"-> {output.relative_to(PROJECT_ROOT)}"
            )
            subprocess.run(command, cwd=PROJECT_ROOT, check=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
