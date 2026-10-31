from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"


def test_start_is_limited_to_a_gated_infrastructure_only_hml_session() -> None:
    workflow = (WORKFLOWS / "environment-start.yml").read_text(encoding="utf-8")

    hml_gate = workflow.split("  hml-gates:", 1)[1].split("  cost-preflight:", 1)[0]
    assert "environment: hml-lifecycle" in hml_gate
    assert "K8S_HML_TERRAFORM_ROOT_READY" in hml_gate
    assert "--window-end-inclusive 2026-11-05" in workflow
    assert "--session-scope infrastructure-only" in workflow
    assert "session_scope" in workflow and "infrastructure-only" in workflow
    assert "environment: operations" in workflow
    role = workflow.index("Configure the narrow lifecycle start role")
    authorize = workflow.index("lifecycle_session_ledger.py authorize-open")
    assert role < authorize
    assert "validate_auth_lambda_preflight.py" not in workflow
    assert "inputs.started_at || 'default-17-BRT'" in workflow
    assert "Apply the exact K8s foundation opening plan" in workflow


def test_hml_gate_has_no_aws_or_actions_token_permissions() -> None:
    workflow = (WORKFLOWS / "environment-start.yml").read_text(encoding="utf-8")
    hml_gate = workflow.split("  hml-gates:", 1)[1].split("  cost-preflight:", 1)[0]

    assert "permissions:\n      contents: read" in hml_gate
    assert "id-token: write" not in hml_gate
    assert "actions: write" not in hml_gate


def test_start_has_no_application_or_public_edge_work() -> None:
    workflow = (WORKFLOWS / "environment-start.yml").read_text(encoding="utf-8").lower()
    for excluded in (
        "deploy-lambda.yml",
        "aws lambda update-function-code",
        "cloudfront",
        "api gateway",
        "edge_jwt",
        "reconcile_public_edge",
        "deploy the application",
    ):
        assert excluded not in workflow


def test_start_dispatches_the_guarded_database_bootstrap_after_hml_infrastructure() -> None:
    workflow = (WORKFLOWS / "environment-start.yml").read_text(encoding="utf-8")
    database_step = workflow.split("      - name: Bootstrap the HML lifecycle database", 1)[1].split(
        "      - name: Record the infrastructure-only opening", 1
    )[0]

    assert workflow.index("Apply the exact HML namespace opening plan") < workflow.index(
        "Bootstrap the HML lifecycle database"
    )
    assert '--repository "$DATABASE_INFRA_REPOSITORY" --workflow apply.yml --ref main' in database_step
    assert "--authorization-action open" in database_step
    assert "session_scope" in database_step
    assert "infrastructure-only" in database_step
    assert "phase" in database_step
    assert "bootstrap" in database_step
    assert "--output-name database_bootstrap" in database_step


def test_stop_is_limited_to_infrastructure_only_hml_and_verifies_teardown() -> None:
    workflow = (WORKFLOWS / "environment-stop.yml").read_text(encoding="utf-8")

    assert "--stage hml" in workflow
    assert "session_scope" in workflow and "infrastructure-only" in workflow
    assert "orphan-audit.yml" in workflow
    assert "lifecycle_session_ledger.py finalize-close" in workflow
    assert "capture_lifecycle_cost.py" in workflow
    for excluded in ("cloudfront", "api gateway", "EDGE_", "reconcile_public_edge"):
        assert excluded.lower() not in workflow.lower()


def test_cleanup_excludes_other_stages_and_scopes() -> None:
    workflow = (WORKFLOWS / "lifecycle-cleanup.yml").read_text(encoding="utf-8")

    assert 'x.get("stage") == "hml"' in workflow
    assert 'x.get("session_scope") == "infrastructure-only"' in workflow
    assert "--limit 100" in workflow
    assert "dispatch_expired_lifecycle_sessions.py" in workflow
    assert "lifecycle-ledger-bootstrap" not in workflow


def test_cleanup_workflow_name_matches_the_ledger_authorization_guard() -> None:
    workflow = (WORKFLOWS / "lifecycle-cleanup.yml").read_text(encoding="utf-8")
    ledger = (ROOT / ".github" / "scripts" / "lifecycle_session_ledger.py").read_text(encoding="utf-8")
    workflow_name = workflow.splitlines()[0].removeprefix("name: ")

    assert workflow_name == "Expired HML lifecycle cleanup"
    assert ledger.count(f'"{workflow_name}"') == 3
    assert "Expired lifecycle session cleanup" not in ledger
