from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_python_agent_is_installed_and_starts_before_uvicorn():
    dependencies = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    deployment = (ROOT / "k8s/base/app/deployment.yaml").read_text(encoding="utf-8")

    assert 'newrelic = ' in dependencies
    assert 'CMD ["newrelic-admin", "run-program", "uvicorn"' in dockerfile
    assert 'command: ["newrelic-admin", "run-program", "uvicorn"' in deployment


def test_hml_apm_configuration_is_bounded_and_excludes_sensitive_data():
    staging_config = (
        ROOT / "k8s/overlays/staging/foundation/configmap-patch.yaml"
    ).read_text(encoding="utf-8")

    expected_settings = (
        'NEW_RELIC_APP_NAME: "auto-shop-api"',
        'NEW_RELIC_ENABLED: "true"',
        'NEW_RELIC_DISTRIBUTED_TRACING_ENABLED: "true"',
        'NEW_RELIC_APPLICATION_LOGGING_FORWARDING_ENABLED: "true"',
        'NEW_RELIC_APPLICATION_LOGGING_FORWARDING_MAX_SAMPLES_STORED: "1000"',
        'NEW_RELIC_CAPTURE_PARAMS: "false"',
        'NEW_RELIC_TRANSACTION_TRACER_RECORD_SQL: "off"',
        'NEW_RELIC_ALLOW_ALL_HEADERS: "false"',
        'NEW_RELIC_LABELS: "environment:hml"',
        'APP_VERSION: "__APP_VERSION__"',
    )
    for setting in expected_settings:
        assert setting in staging_config

    base_config = (ROOT / "k8s/base/foundation/configmap.yaml").read_text(encoding="utf-8")
    assert 'NEW_RELIC_ENABLED: "false"' in base_config
    agent_config = (ROOT / "newrelic.ini").read_text(encoding="utf-8")
    assert "[import-hook:logging]" in agent_config
    assert "enabled = false" in agent_config


def test_hml_license_key_is_delivered_only_through_a_dedicated_secret():
    deployment = (ROOT / "k8s/base/app/deployment.yaml").read_text(encoding="utf-8")
    staging_patch = (
        ROOT / "k8s/overlays/staging/app/new-relic-patch.yaml"
    ).read_text(encoding="utf-8")
    workflow = (ROOT / ".github/workflows/cd-staging.yml").read_text(encoding="utf-8")
    deploy_script = (ROOT / "k8s/scripts/deploy.sh").read_text(encoding="utf-8")

    assert "NEW_RELIC_LICENSE_KEY" not in deployment
    assert "secretKeyRef:" in staging_patch
    assert "name: auto-shop-new-relic" in staging_patch
    assert "key: NEW_RELIC_LICENSE_KEY" in staging_patch
    assert "secrets.NEW_RELIC_LICENSE_KEY" in workflow
    assert '--from-file="NEW_RELIC_LICENSE_KEY=${license_file}"' in deploy_script
    assert "apply_phase foundation\nensure_new_relic_secret" in deploy_script
    assert "--from-literal" not in workflow
    assert "--from-literal" not in deploy_script
    powershell_deploy = (ROOT / "k8s/scripts/deploy.ps1").read_text(encoding="utf-8")
    assert '"NEW_RELIC_LICENSE_KEY=$licenseFile"' in powershell_deploy
    assert '"staging" { "auto-shop-hml" }' in powershell_deploy
    assert '"production" { "auto-shop-prd" }' in powershell_deploy


def test_deploy_scripts_materialize_the_immutable_image_as_application_version():
    bash_deploy = (ROOT / "k8s/scripts/deploy.sh").read_text(encoding="utf-8")
    powershell_deploy = (ROOT / "k8s/scripts/deploy.ps1").read_text(encoding="utf-8")

    assert 'rendered//__APP_VERSION__/${IMAGE_REFERENCE}' in bash_deploy
    assert '.Replace("__APP_VERSION__", $ImageReference)' in powershell_deploy
