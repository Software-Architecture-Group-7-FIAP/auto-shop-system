from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"


def test_cluster_smoke_reports_failed_migration_jobs_without_waiting_for_timeout() -> None:
    workflow = CI_WORKFLOW.read_text(encoding="utf-8")
    migration_step = workflow.split(
        "      - name: Run migration before API rollout", maxsplit=1
    )[1].split("      - name: Smoke test liveness, readiness, and docs", maxsplit=1)[0]

    assert "wait_for_job \"auto-shop-migrate\" 600" in migration_step
    assert 'conditions[?(@.status=="True")].type' in migration_step
    assert "Failed)" in migration_step
    assert "kubectl describe job" in migration_step
    assert "kubectl logs" in migration_step
    assert "kubectl wait --for=condition=complete job/auto-shop-migrate" not in migration_step
