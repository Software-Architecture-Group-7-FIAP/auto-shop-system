from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"


def test_cluster_smoke_reports_failed_migration_jobs_without_waiting_for_timeout() -> (
    None
):
    workflow = CI_WORKFLOW.read_text(encoding="utf-8")
    migration_step = workflow.split(
        "      - name: Run migration before API rollout", maxsplit=1
    )[1].split("      - name: Smoke test liveness, readiness, and docs", maxsplit=1)[0]
    waiter = (ROOT / "k8s/scripts/wait-for-job.sh").read_text(encoding="utf-8")

    assert (
        "bash k8s/scripts/wait-for-job.sh auto-shop-migrate auto-shop 600"
        in migration_step
    )
    assert "FailureTarget" in waiter
    assert "Failed" in waiter
    assert "failed_count > backoff_limit" in waiter
    assert "--request-timeout=5s" in waiter
    assert "sleep 2" in waiter
    assert "describe job" in waiter
    assert (
        "kubectl wait --for=condition=complete job/auto-shop-migrate"
        not in migration_step
    )


def test_cluster_smoke_reports_live_job_progress_with_redacted_recent_logs() -> None:
    workflow = CI_WORKFLOW.read_text(encoding="utf-8")
    migration_step = workflow.split(
        "      - name: Run migration before API rollout", maxsplit=1
    )[1].split("      - name: Smoke test liveness, readiness, and docs", maxsplit=1)[0]
    waiter = (ROOT / "k8s/scripts/wait-for-job.sh").read_text(encoding="utf-8")

    assert (
        "bash k8s/scripts/wait-for-job.sh auto-shop-migrate auto-shop 600"
        in migration_step
    )
    assert "report_job_progress" in waiter
    assert "get job" in waiter
    assert "get pods" in waiter
    assert "--since=15s" in waiter
    assert "redact_output" in waiter
    assert "postgres(ql)?" in waiter
    assert "next_report_seconds=$((elapsed_seconds + 10))" in waiter


def test_hml_and_production_deployments_use_the_shared_job_waiter() -> None:
    deploy_script = (ROOT / "k8s/scripts/deploy.sh").read_text(encoding="utf-8")

    assert (
        'bash "${REPO_ROOT}/k8s/scripts/wait-for-job.sh" "${MIGRATION_JOB}" "${NAMESPACE}" 300'
        in deploy_script
    )
    assert (
        'bash "${REPO_ROOT}/k8s/scripts/wait-for-job.sh" "${SEED_JOB}" "${NAMESPACE}" 300'
        in deploy_script
    )
    assert (
        'kubectl wait --for=condition=complete "job/${MIGRATION_JOB}"'
        not in deploy_script
    )


def test_migration_job_does_not_restart_failed_processes_after_its_own_retries() -> (
    None
):
    manifest = (ROOT / "k8s/base/migration/migrate-job.yaml").read_text(
        encoding="utf-8"
    )

    assert "backoffLimit: 0" in manifest
    assert "restartPolicy: Never" in manifest
    assert "attempt=1;" in manifest
    assert 'attempt" -le 5' in manifest
