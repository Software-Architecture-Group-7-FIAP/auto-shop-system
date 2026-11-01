from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"


def test_staging_and_production_deploy_require_coordinator_dispatch() -> None:
    for filename, deploy_job, frontend_job in (
        ("cd-staging.yml", "deploy-staging:", "deploy-staging-frontend:"),
        ("cd-prod.yml", "deploy-production:", "deploy-production-frontend:"),
    ):
        workflow = (WORKFLOWS / filename).read_text(encoding="utf-8")
        deployment = workflow.split(f"  {deploy_job}\n", 1)[1].split(
            f"\n  {frontend_job}", 1
        )[0]

        assert "github.event_name == 'workflow_dispatch'" in deployment
        assert "needs.lifecycle-authorization.result == 'success'" in deployment
        assert "github.event_name == 'push'" not in deployment
        assert "push-deploy-gated:" in workflow
        assert "validate_environment_window.py --action" in deployment


def test_frontend_deploy_gate_is_independent_from_backend_deploy_gate() -> None:
    for filename, backend_job, frontend_job, next_job, gate in (
        (
            "cd-staging.yml",
            "deploy-staging:",
            "deploy-staging-frontend:",
            "deploy-staging-frontend-skipped:",
            "DEPLOY_STAGING_FRONTEND_ENABLED",
        ),
        (
            "cd-prod.yml",
            "deploy-production:",
            "deploy-production-frontend:",
            "deploy-production-skipped:",
            "DEPLOY_PRODUCTION_FRONTEND_ENABLED",
        ),
    ):
        workflow = (WORKFLOWS / filename).read_text(encoding="utf-8")
        authorization = workflow.split("  build-push:", 1)[0]
        backend = workflow.split(f"  {backend_job}\n", 1)[1].split(
            f"\n  {frontend_job}", 1
        )[0]
        frontend = workflow.split(f"  {frontend_job}\n", 1)[1].split(
            f"\n  {next_job}", 1
        )[0]

        assert gate not in authorization
        assert gate not in backend
        assert f"vars.{gate} == 'true'" in frontend


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
