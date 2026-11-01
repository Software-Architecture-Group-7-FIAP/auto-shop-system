from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
VALUES = ROOT / "k8s/observability/new-relic/values-staging.yaml"


def test_hml_kubernetes_bundle_is_pinned_minimal_and_cost_bounded():
    values = VALUES.read_text(encoding="utf-8")
    bash_deploy = (ROOT / "k8s/scripts/deploy.sh").read_text(encoding="utf-8")

    assert 'NEW_RELIC_K8S_CHART_VERSION="8.0.39"' in bash_deploy
    assert 'NEW_RELIC_K8S_CHART="newrelic/nri-bundle"' in bash_deploy
    assert 'NEW_RELIC_K8S_CHART_SHA256="96eb019f' in bash_deploy
    assert 'cluster: "auto-shop-hml"' in values
    assert "lowDataMode: true" in values
    assert "newrelic-infrastructure:\n  enabled: true" in values
    assert "controlPlane:\n    enabled: false" in values
    assert "kube-state-metrics:\n  enabled: true" in values

    for component in (
        "nri-prometheus",
        "nri-metadata-injection",
        "nri-kube-events",
        "newrelic-logging",
        "newrelic-pixie",
        "nr-ebpf-agent",
        "k8s-agents-operator",
        "newrelic-prometheus-agent",
        "newrelic-k8s-metrics-adapter",
    ):
        assert f"{component}:\n  enabled: false" in values


def test_bundle_reuses_approved_secret_without_rendering_credentials():
    values = VALUES.read_text(encoding="utf-8")
    bash_deploy = (ROOT / "k8s/scripts/deploy.sh").read_text(encoding="utf-8")
    powershell_deploy = (ROOT / "k8s/scripts/deploy.ps1").read_text(encoding="utf-8")

    assert 'customSecretName: "auto-shop-new-relic"' in values
    assert 'customSecretLicenseKey: "NEW_RELIC_LICENSE_KEY"' in values
    assert "licenseKey:" not in values
    assert "data:" not in values
    assert "stringData:" not in values
    assert "--set" not in bash_deploy
    assert "--set" not in powershell_deploy
    assert "--from-literal" not in bash_deploy
    assert "--from-literal" not in powershell_deploy


def test_bundle_install_is_atomic_and_bounded_to_staging_lifecycle():
    bash_deploy = (ROOT / "k8s/scripts/deploy.sh").read_text(encoding="utf-8")
    powershell_deploy = (ROOT / "k8s/scripts/deploy.ps1").read_text(encoding="utf-8")
    workflow = (ROOT / ".github/workflows/cd-staging.yml").read_text(encoding="utf-8")

    assert '[[ "${ENVIRONMENT}" == "staging" ]] || return 0' in bash_deploy
    assert 'helm upgrade --install "${NEW_RELIC_K8S_RELEASE}"' in bash_deploy
    assert "sha256sum --check --status" in bash_deploy
    for flag in ("--atomic", "--wait", "--timeout 10m", "--namespace \"${NAMESPACE}\""):
        assert flag in bash_deploy
    assert bash_deploy.index("apply_phase app") < bash_deploy.rindex(
        "install_new_relic_kubernetes"
    )
    assert 'if ($Environment -ne "staging")' in powershell_deploy
    assert 'Invoke-RequiredCommand "helm"' in powershell_deploy
    assert "azure/setup-helm@1a275c3b69536ee54be43f2070a358922e12c8d4" in workflow
    assert "version: v3.19.0" in workflow


def test_runbook_defers_live_validation_and_covers_issue_3_signals():
    runbook = (ROOT / "docs/observability/new-relic-kubernetes.md").read_text(
        encoding="utf-8"
    )

    for required_text in (
        "approved HML session",
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
