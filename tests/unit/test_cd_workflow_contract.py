from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"


def test_staging_and_production_deploy_from_their_branch_pushes() -> None:
    for filename, deploy_job in (
        ("cd-staging.yml", "deploy-staging:"),
        ("cd-prod.yml", "deploy-production:"),
    ):
        workflow = (WORKFLOWS / filename).read_text(encoding="utf-8")
        assert deploy_job in workflow
        assert "github.event_name == 'push'" in workflow
        assert "push-deploy-gated:" not in workflow
        assert "validate_environment_window.py --action deploy" in workflow


def test_frontend_deploy_gate_is_independent_from_backend_deploy_gate() -> None:
    staging = (WORKFLOWS / "cd-staging.yml").read_text(encoding="utf-8")
    production = (WORKFLOWS / "cd-prod.yml").read_text(encoding="utf-8")
    assert "DEPLOY_STAGING_FRONTEND_ENABLED" not in staging.split(
        "  build-push:", 1
    )[0]
    assert "DEPLOY_PRODUCTION_FRONTEND_ENABLED" not in production.split(
        "  build-push:", 1
    )[0]


def test_hml_wait_does_not_run_after_a_failed_open() -> None:
    workflow = (WORKFLOWS / "environment-start.yml").read_text(encoding="utf-8")
    wait_job = workflow.split("  hml-auto-stop-wait:\n", 1)[1].split(
        "  hml-auto-stop-close:\n", 1
    )[0]

    assert "needs.open.result == 'success'" in wait_job
    assert "always()" not in wait_job


def test_reusable_frontend_uses_the_hml_environment_authorization() -> None:
    workflow = (WORKFLOWS / "reusable-frontend-deploy.yml").read_text(encoding="utf-8")

    assert "ENVIRONMENT_ACTIVE_HML" in workflow
    assert "GITHUB_ENVIRONMENT" in workflow
    assert "python3 ../.github/scripts/validate_environment_window.py --action deploy" in workflow
