from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_hml_app_deploy_materializes_new_relic_secret_without_installing_cluster_chart():
    bash_deploy = (ROOT / "k8s/scripts/deploy.sh").read_text(encoding="utf-8")
    powershell_deploy = (ROOT / "k8s/scripts/deploy.ps1").read_text(encoding="utf-8")
    cd_workflow = (ROOT / ".github/workflows/cd-staging.yml").read_text(encoding="utf-8")
    minimal_workflow = (ROOT / ".github/workflows/deploy-hml-minimal.yml").read_text(encoding="utf-8")

    assert "ensure_new_relic_secret" in bash_deploy
    assert "ensure_new_relic_secret" in bash_deploy.split("apply_phase foundation", maxsplit=1)[1]
    assert "function Ensure-NewRelicSecret" in powershell_deploy
    assert "Ensure-NewRelicSecret" in powershell_deploy
    for script in (bash_deploy, powershell_deploy):
        assert "helm upgrade" not in script
        assert "nri-bundle" not in script
        assert "NEW_RELIC_LICENSE_KEY" in script
        assert "--from-literal" not in script

    assert "NEW_RELIC_LICENSE_KEY: ${{ secrets.NEW_RELIC_LICENSE_KEY }}" in cd_workflow
    assert "NEW_RELIC_LICENSE_KEY: ${{ secrets.NEW_RELIC_LICENSE_KEY }}" in minimal_workflow
    assert "setup-helm" not in cd_workflow
    assert "setup-helm" not in minimal_workflow


def test_runbook_assigns_cluster_chart_to_platform_and_preserves_hml_acceptance_signals():
    runbook = (ROOT / "docs/observability/new-relic-kubernetes.md").read_text(
        encoding="utf-8"
    )

    for required_text in (
        "k8s-infra",
        "envs/staging/platform",
        "cluster-ci.yml",
        "cluster-apply.yml",
        "approved HML session",
        "nri-bundle",
        "8.0.39",
        "96eb019f7c78e1e746e0ba170b7e656e437ae3f7bfe7203f812e750511db108f",
        "K8sClusterSample",
        "K8sNodeSample",
        "K8sPodSample",
        "K8sContainerSample",
        "K8sHpaSample",
        "cpuUsedCores",
        "memoryWorkingSetBytes",
        "isReady",
        "restartCount",
        "currentReplicas",
        "desiredReplicas",
        "environment-stop.yml",
    ):
        assert required_text in runbook
