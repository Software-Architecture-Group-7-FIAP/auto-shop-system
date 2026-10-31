from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / ".github" / "scripts" / "cross_repo_lifecycle.py"
SPEC = importlib.util.spec_from_file_location("cross_repo_lifecycle", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
LIFECYCLE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(LIFECYCLE)


def test_cancel_wait_stops_retrying_api_errors_at_its_finite_deadline(monkeypatch: pytest.MonkeyPatch) -> None:
    now = 0.0
    polls = 0

    def monotonic() -> float:
        return now

    def sleep(seconds: float) -> None:
        nonlocal now
        now += seconds

    def unavailable(*_args: object, **_kwargs: object) -> dict[str, object]:
        nonlocal polls
        polls += 1
        raise LIFECYCLE.LifecycleDispatchError("GitHub API could not be reached.")

    monkeypatch.setattr(LIFECYCLE.time, "monotonic", monotonic)
    monkeypatch.setattr(LIFECYCLE.time, "sleep", sleep)
    monkeypatch.setattr(LIFECYCLE, "_get_run", unavailable)

    with pytest.raises(LIFECYCLE.LifecycleDispatchError, match="did not reach completed"):
        LIFECYCLE._wait_for_cancelled_run(
            "token", "org/repo", 42, "session:dispatch", "", poll_seconds=10, wait_seconds=25
        )

    assert now == 25
    assert polls == 3


def test_cancel_wait_reports_completed_run_and_cancellation_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        LIFECYCLE,
        "_get_run",
        lambda *_args, **_kwargs: {"id": 42, "status": "completed", "conclusion": "cancelled"},
    )

    with pytest.raises(LIFECYCLE.LifecycleDispatchError, match="conclusion 'cancelled'.*permission denied"):
        LIFECYCLE._wait_for_cancelled_run(
            "token",
            "org/repo",
            42,
            "session:dispatch",
            "permission denied",
            poll_seconds=10,
            wait_seconds=25,
        )


def test_stop_workflow_reserves_audit_window_and_runs_audit_after_teardown_failure() -> None:
    workflow = (ROOT / ".github" / "workflows" / "environment-stop.yml").read_text(encoding="utf-8")
    resolver = (ROOT / ".github" / "scripts" / "resolve_lifecycle_session.py").read_text(encoding="utf-8")
    coordinator = (ROOT / ".github" / "scripts" / "cross_repo_lifecycle.py").read_text(encoding="utf-8")
    cancel_deploy = (ROOT / ".github" / "scripts" / "cancel_lifecycle_app_deploys.py").read_text(encoding="utf-8")
    edge_reconcile = (ROOT / ".github" / "scripts" / "reconcile_public_edge.sh").read_text(encoding="utf-8")
    assert "AUDIT_RESERVE = timedelta(minutes=15)" in resolver
    assert "TEARDOWN_MARGIN = timedelta(minutes=5)" in resolver
    assert "teardown_deadline_utc" in resolver
    assert "teardown_allowed=" in resolver
    assert "audit_start_utc=" in resolver
    assert "resolve_session:" in workflow
    assert "audit:" in workflow
    assert "if: always() && needs.resolve_session.outputs.session_authorized == 'true'" in workflow
    assert "if: needs.resolve_session.result == 'success' && needs.resolve_session.outputs.teardown_allowed == 'true'" in workflow
    assert workflow.count('--deadline-utc "$TEARDOWN_END"') == 9
    assert "--deadline-utc \"$CLEANUP_END\"" in workflow
    assert "default=30" in coordinator
    assert "--deadline-utc \"$TEARDOWN_END\"" in workflow
    assert "--deadline-utc" in cancel_deploy
    assert "timeout --signal=INT --kill-after=15s" in edge_reconcile
    assert "assert_lifecycle_deadline.py" in workflow

    audit_job = workflow.split("  audit:\n", 1)[1]
    assert "timeout-minutes: 70" in audit_job
    assert "wait_until_utc.py" in audit_job
    assert "--target-utc \"$AUDIT_START\"" in audit_job
    assert "assert_no_active_lifecycle_runs.py" in audit_job
    assert audit_job.index("wait_until_utc.py") < audit_job.index("assert_no_active_lifecycle_runs.py")
    assert "assert_no_active_lifecycle_runs.py --wait-seconds 60 --poll-seconds 15" in audit_job
    assert audit_job.index("assert_no_active_lifecycle_runs.py") < audit_job.index("--workflow orphan-audit.yml")


def test_open_workflow_preflights_persistent_auth_lambdas_before_cross_repo_dispatch() -> None:
    workflow = (ROOT / ".github" / "workflows" / "environment-start.yml").read_text(encoding="utf-8")
    validation = workflow.index("Validate persistent customer auth Lambdas before opening session resources")
    dispatch = workflow.index(".github/scripts/cross_repo_lifecycle.py")

    assert "role/auto-shop-staging-github-auth-preflight" in workflow
    assert "validate_auth_lambda_preflight.py" in workflow
    assert validation < dispatch


def test_auth_preflight_role_is_read_only_and_scoped_to_exact_resources() -> None:
    configuration = (ROOT / "infra" / "aws" / "github_oidc.tf").read_text(encoding="utf-8")
    workflow = (ROOT / ".github" / "workflows" / "environment-start.yml").read_text(encoding="utf-8")

    assert 'variable = "token.actions.githubusercontent.com:aud"' in configuration
    assert 'values   = ["sts.amazonaws.com"]' in configuration
    assert 'values   = ["${local.github_oidc_subject_prefix}:environment:operations"]' in configuration
    assert 'actions = ["ssm:GetParameters"]' in configuration
    assert 'actions = ["lambda:GetFunctionConfiguration"]' in configuration
    assert 'name                 = "auto-shop-staging-github-auth-preflight"' in configuration
    assert "parameter/auto-shop/staging/network/workload-private-subnet-ids" in configuration
    assert "parameter/auto-shop/staging/network/lambda-security-group-id" in configuration
    assert "parameter/auto-shop/staging/network/vpc-id" in configuration
    assert "parameter/auto-shop/staging/auth/customer-token/function-arn/hml" in configuration
    assert "parameter/auto-shop/staging/auth/customer-token/function-arn/prd" in configuration
    assert "ssm:GetParametersByPath" not in configuration
    assert "github_auth_preflight_role_arn" in configuration
    assert "role/auto-shop-staging-github-auth-preflight" in workflow


def test_upstream_ssm_prefix_matches_the_auth_preflight_contract() -> None:
    variables = (ROOT / "infra" / "aws" / "variables.tf").read_text(encoding="utf-8")
    upstream_prefix = variables.split('variable "upstream_ssm_prefix" {', 1)[1].split("\n}", 1)[0]

    assert 'condition     = var.upstream_ssm_prefix == "/auto-shop/staging"' in upstream_prefix


def test_private_ghcr_images_are_verified_and_mirrored_before_eks_deploy() -> None:
    for workflow_name, deploy_command in (
        ("cd-staging.yml", "./k8s/scripts/deploy.sh staging"),
        ("cd-prod.yml", "./k8s/scripts/deploy.sh production"),
    ):
        workflow = (ROOT / ".github" / "workflows" / workflow_name).read_text(encoding="utf-8")
        mirror = workflow.index("scripts/mirror_ghcr_image_to_ecr.py")
        deploy = workflow.index(deploy_command)

        assert "packages: read" in workflow
        assert "GITHUB_TOKEN: ${{ github.token }}" in workflow
        assert mirror < deploy
        assert "IMAGE_REFERENCE: ${{ steps.ecr_image.outputs.image_reference }}" in workflow
