import argparse
import re
from pathlib import Path


UNSAFE_PATTERNS = {
    "DEV_ADMIN_PASSWORD=admin123",
    "POSTGRES_PASSWORD: oficina",
    "postgresql://oficina:oficina@",
    "SECRET_KEY=dev-secret-key",
    "SECRET_KEY=change-me",
}

CHECKED_FILES = (
    Path("docker-compose.yml"),
    Path("src/config.py"),
    Path("README.md"),
)

PRODUCTION_MANIFEST_ROOTS = (
    Path("k8s/base"),
    Path("k8s/overlays/staging"),
    Path("k8s/overlays/production"),
)

IMMUTABLE_IMAGE = re.compile(r"(?:@sha256:[0-9a-f]{64}|:[0-9a-f]{7,64})$")


def production_manifest_findings(image_reference: str | None) -> list[str]:
    findings: list[str] = []
    for root in PRODUCTION_MANIFEST_ROOTS:
        if not root.exists():
            continue
        for path in root.rglob("*.yaml"):
            content = path.read_text(encoding="utf-8")
            lower_content = content.lower()
            if any(value in lower_content for value in ("http://", "localhost", "mailhog")):
                findings.append(f"{path}: production-like manifests contain a local or HTTP value")
            if ":latest" in lower_content:
                findings.append(f"{path}: mutable image tag latest is not allowed")
            if "secrets.example" in lower_content or (
                "__image_tag__" in lower_content and not image_reference
            ):
                findings.append(f"{path}: unresolved deployment placeholder")

    if image_reference and not IMMUTABLE_IMAGE.search(image_reference):
        findings.append("image reference must end in a digest or hexadecimal commit-SHA tag")
    return findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--image-reference",
        help="release image digest or hexadecimal commit-SHA tag used to resolve production manifests",
    )
    args = parser.parse_args()
    findings: list[str] = []
    for path in CHECKED_FILES:
        if not path.exists():
            continue
        content = path.read_text(encoding="utf-8")
        for pattern in UNSAFE_PATTERNS:
            if pattern in content:
                findings.append(f"{path}: contains unsafe default {pattern!r}")

    findings.extend(production_manifest_findings(args.image_reference))

    if findings:
        print("Unsafe defaults found:")
        for finding in findings:
            print(f"- {finding}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
