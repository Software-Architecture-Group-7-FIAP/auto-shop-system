from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"


def _k8s_workflow_paths(workflow_text: str) -> list[str]:
    return re.findall(
        r'--repository "\$K8S_INFRA_REPOSITORY" --workflow ([a-z-]+\.yml) --ref main',
        workflow_text,
    )


def test_start_keeps_foundation_hosted_then_routes_platform_and_hml_to_private_runner() -> None:
    workflow = (WORKFLOWS / "environment-start.yml").read_text(encoding="utf-8")

    assert _k8s_workflow_paths(workflow) == [
        "ci.yml",
        "apply.yml",
        "cluster-ci.yml",
        "cluster-apply.yml",
        "cluster-ci.yml",
        "cluster-apply.yml",
    ]
    assert "K8S_PRIVATE_RUNNER_PREREQUISITES_READY" in workflow


def test_stop_destroys_cluster_before_disabling_nat() -> None:
    workflow = (WORKFLOWS / "environment-stop.yml").read_text(encoding="utf-8")
    paths = _k8s_workflow_paths(workflow)

    assert paths == [
        "cluster-destroy.yml",
        "cluster-destroy.yml",
        "cluster-destroy.yml",
        "cluster-destroy.yml",
        "destroy.yml",
        "destroy.yml",
        "ci.yml",
        "apply.yml",
        "orphan-audit.yml",
    ]
    assert workflow.index("Plan compute-only foundation teardown") < workflow.index("Plan NAT shutdown")
    assert workflow.index("Apply the reviewed compute-only foundation teardown plan") < workflow.index(
        "Apply the reviewed NAT shutdown plan"
    )
