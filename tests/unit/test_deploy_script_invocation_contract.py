from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_deployment_workflows_invoke_deploy_script_through_bash():
    expected_commands = {
        ".github/workflows/cd-staging.yml": (
            "run: bash ./k8s/scripts/deploy.sh staging "
            '"${IMAGE_REFERENCE}"'
        ),
        ".github/workflows/cd-prod.yml": (
            "run: bash ./k8s/scripts/deploy.sh production "
            '"${IMAGE_REFERENCE}" yes'
        ),
        ".github/workflows/deploy-hml-minimal.yml": (
            "run: bash ./k8s/scripts/deploy.sh staging "
            '"${IMAGE_REFERENCE}"'
        ),
    }

    for workflow_path, command in expected_commands.items():
        workflow = (ROOT / workflow_path).read_text(encoding="utf-8")

        assert command in workflow
        assert "run: ./k8s/scripts/deploy.sh" not in workflow
