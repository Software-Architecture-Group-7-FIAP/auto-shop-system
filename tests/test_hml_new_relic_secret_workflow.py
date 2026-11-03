from pathlib import Path
import unittest


WORKFLOW = (
    Path(__file__).resolve().parents[1]
    / ".github"
    / "workflows"
    / "deploy-hml-minimal.yml"
)


class HmlNewRelicSecretWorkflowTests(unittest.TestCase):
    def test_manual_operation_keeps_deploy_as_default_and_adds_secret_preparation(self) -> None:
        content = WORKFLOW.read_text(encoding="utf-8")
        inputs = content.split("    inputs:", maxsplit=1)[1].split("\n\npermissions:", maxsplit=1)[0]

        self.assertIn("default: deploy", inputs)
        self.assertIn("- deploy", inputs)
        self.assertIn("- prepare-newrelic-secret", inputs)
        self.assertIn("inputs.operation == 'prepare-newrelic-secret'", content)

    def test_secret_preparation_uses_the_existing_hml_environment_and_private_runner(self) -> None:
        content = WORKFLOW.read_text(encoding="utf-8")
        job = content.split("\n  prepare-hml-newrelic-secret:\n", maxsplit=1)[1].split(
            "\n  deploy-hml:\n", maxsplit=1
        )[0]

        self.assertIn("environment: hml", job)
        self.assertIn("group: k8s-private-eks", job)
        self.assertIn("codebuild-auto-shop-hml-private-runner-", job)
        self.assertIn("id-token: write", job)
        self.assertIn("NEW_RELIC_LICENSE_KEY: ${{ secrets.NEW_RELIC_LICENSE_KEY }}", job)
        self.assertNotIn("mirror_ghcr_image_to_ecr.py", job)
        self.assertNotIn("k8s/scripts/deploy.sh", job)

    def test_secret_preparation_fails_closed_and_never_passes_the_value_on_a_command_line(self) -> None:
        content = WORKFLOW.read_text(encoding="utf-8")
        job = content.split("\n  prepare-hml-newrelic-secret:\n", maxsplit=1)[1].split(
            "\n  deploy-hml:\n", maxsplit=1
        )[0]
        check = job.split("- name: Require the HML New Relic license secret", maxsplit=1)[1].split(
            "\n      - ", maxsplit=1
        )[0]
        materialize = job.split("- name: Materialize the HML New Relic Kubernetes Secret", maxsplit=1)[1]

        self.assertIn('[[ -n "$NEW_RELIC_LICENSE_KEY" ]]', check)
        self.assertIn("auto-shop-new-relic", materialize)
        self.assertIn('--from-file=NEW_RELIC_LICENSE_KEY="$license_file"', materialize)
        self.assertIn("unset NEW_RELIC_LICENSE_KEY", materialize)
        self.assertIn("kubectl apply --filename=-", materialize)
        self.assertNotIn("--from-literal", materialize)
        self.assertNotIn('echo "$NEW_RELIC_LICENSE_KEY"', materialize)
        self.assertLess(job.index("Require the HML New Relic license secret"), job.index("Configure AWS credentials"))

    def test_run_title_stays_within_the_existing_hml_webhook_allowlist(self) -> None:
        content = WORKFLOW.read_text(encoding="utf-8")

        self.assertRegex(content, r"(?m)^run-name: HML deploy \\$\\{\\{ github\\.sha \\}\\}$")

    def test_summary_reports_prepare_only_runs_as_their_own_operation(self) -> None:
        content = WORKFLOW.read_text(encoding="utf-8")
        summary = content.split("\n  summary:\n", maxsplit=1)[1]

        self.assertIn("PREPARE_RESULT", summary)
        self.assertIn("inputs.operation", summary)
        self.assertIn("prepare-newrelic-secret", summary)


if __name__ == "__main__":
    unittest.main()
