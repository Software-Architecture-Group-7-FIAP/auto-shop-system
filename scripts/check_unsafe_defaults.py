from pathlib import Path


UNSAFE_PATTERNS = {
    "DEV_ADMIN_PASSWORD=admin123",
    "POSTGRES_PASSWORD: oficina",
    "postgresql://oficina:oficina@",
    "SECRET_KEY=dev-secret-key",
    "SECRET_KEY=change-me",
}

CHECKED_FILES = (
    Path(".env.example"),
    Path("docker-compose.yml"),
    Path("src/config.py"),
)


def main() -> int:
    findings: list[str] = []
    for path in CHECKED_FILES:
        if not path.exists():
            continue
        content = path.read_text(encoding="utf-8")
        for pattern in UNSAFE_PATTERNS:
            if pattern in content:
                findings.append(f"{path}: contains unsafe default {pattern!r}")

    if findings:
        print("Unsafe defaults found:")
        for finding in findings:
            print(f"- {finding}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
