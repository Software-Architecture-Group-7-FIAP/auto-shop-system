import json
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


def test_start_provisions_database_before_hml_identity_then_bootstraps_credentials() -> None:
    workflow = (WORKFLOWS / "environment-start.yml").read_text(encoding="utf-8")
    provision_step = workflow.split("      - name: Provision the HML database role and SSM contract", 1)[1].split(
        "      - name: Plan the isolated HML namespace opening", 1
    )[0]
    bootstrap_step = workflow.split("      - name: Bootstrap the HML lifecycle database", 1)[1].split(
        "      - name: Record the infrastructure-only opening", 1
    )[0]

    assert workflow.index("Apply the exact K8s platform opening plan") < workflow.index(
        "Provision the HML database role and SSM contract"
    )
    assert workflow.index("Provision the HML database role and SSM contract") < workflow.index(
        "Plan the isolated HML namespace opening"
    )
    assert workflow.index("Apply the exact HML namespace opening plan") < workflow.index(
        "Bootstrap the HML lifecycle database"
    )

    for step, phase, output in (
        (provision_step, "provision", "database_provision"),
        (bootstrap_step, "bootstrap", "database_bootstrap"),
    ):
        assert '--repository "$DATABASE_INFRA_REPOSITORY" --workflow apply.yml --ref main' in step
        assert "--authorization-action open" in step
        assert "session_scope" not in step
        dispatch_input_line = next(line for line in step.splitlines() if "--inputs " in line)
        serialized_inputs = dispatch_input_line.split("--inputs ", 1)[1].strip()
        dispatch_inputs = json.loads(json.loads(serialized_inputs))
        assert set(dispatch_inputs) == {"session_id", "started_at", "session_mode", "phase"}
        assert dispatch_inputs["phase"] == phase
        assert f"--output-name {output}" in step
    assert "--session-scope infrastructure-only" in workflow


def test_start_child_dispatches_match_declared_workflow_input_contracts() -> None:
    workflow = (WORKFLOWS / "environment-start.yml").read_text(encoding="utf-8")
    dispatch_lines = [line for line in workflow.splitlines() if "--inputs " in line]

    assert len(dispatch_lines) == 8
    assert all("session_scope" not in line for line in dispatch_lines)


def test_stop_is_limited_to_infrastructure_only_hml_and_verifies_teardown() -> None:
    workflow = (WORKFLOWS / "environment-stop.yml").read_text(encoding="utf-8")
    close_job = workflow.split("  close:\n", 1)[1].split("  audit:\n", 1)[0]
    audit_job = workflow.split("  audit:\n", 1)[1].split("  post-cost-capture:\n", 1)[0]

    assert "--stage hml" in workflow
    assert "REQUESTED_SESSION_SCOPE" in workflow and "infrastructure-only" in workflow
    assert "orphan-audit.yml" in workflow
    assert "lifecycle_session_ledger.py finalize-close" in workflow
    assert "capture_lifecycle_cost.py" in workflow
    assert workflow.index("Apply the reviewed HML namespace teardown plan") < workflow.index(
        "Destroy the ephemeral HML database"
    )
    assert workflow.index("Destroy the ephemeral HML database") < workflow.index(
        "Plan the full K8s platform teardown"
    )
    assert "teardown_needed: ${{ steps.close_decision.outputs.teardown_needed }}" in close_job
    assert "Record when no teardown is needed" in close_job
    for step_name in (
        "Validate the HML cross-repository teardown configuration",
        "Plan the isolated HML namespace teardown",
        "Apply the reviewed HML namespace teardown plan",
        "Destroy the ephemeral HML database",
        "Plan the full K8s platform teardown",
        "Apply the reviewed K8s platform teardown plan",
        "Plan compute-only foundation teardown",
        "Apply the reviewed compute-only foundation teardown plan",
        "Plan NAT shutdown",
        "Apply the reviewed NAT shutdown plan",
    ):
        step = close_job.split(f"      - name: {step_name}", 1)[1].split("      - name:", 1)[0]
        assert "steps.close_decision.outputs.teardown_needed == 'true'" in step
    assert "needs.close.outputs.close_needed == 'true'" in audit_job
    assert "Finalize the ledger only after teardown and orphan audit succeed" in audit_job
    assert "steps.orphan_audit.outcome == 'success'" in audit_job
    dispatch_lines = [line for line in workflow.splitlines() if "--inputs " in line]
    assert dispatch_lines
    assert all("session_scope" not in line for line in dispatch_lines)
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
