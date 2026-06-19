import ast
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"

DOMAIN_FORBIDDEN_IMPORTS = (
    "fastapi",
    "pydantic",
    "sqlalchemy",
    "src.api",
    "src.application",
    "src.infrastructure",
)
APPLICATION_SERVICE_FORBIDDEN_IMPORTS = (
    "fastapi",
    "sqlalchemy",
    "src.api",
    "src.infrastructure",
)


def python_files_under(path: Path) -> list[Path]:
    return sorted(file for file in path.rglob("*.py") if file.name != "__init__.py")


def imported_modules(file_path: Path) -> list[str]:
    tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
    return modules


def is_forbidden_import(module: str, forbidden: tuple[str, ...]) -> bool:
    return any(module == blocked or module.startswith(f"{blocked}.") for blocked in forbidden)


def collect_violations(root: Path, forbidden: tuple[str, ...]) -> list[str]:
    violations = []
    for file_path in python_files_under(root):
        for module in imported_modules(file_path):
            if is_forbidden_import(module, forbidden):
                relative_path = file_path.relative_to(PROJECT_ROOT)
                violations.append(f"{relative_path}: {module}")
    return violations


def test_domain_does_not_depend_on_outer_layers_or_frameworks():
    violations = collect_violations(SRC_ROOT / "domain", DOMAIN_FORBIDDEN_IMPORTS)

    assert violations == []


def test_application_services_do_not_depend_on_api_or_infrastructure():
    violations = collect_violations(
        SRC_ROOT / "application" / "services",
        APPLICATION_SERVICE_FORBIDDEN_IMPORTS,
    )

    assert violations == []
