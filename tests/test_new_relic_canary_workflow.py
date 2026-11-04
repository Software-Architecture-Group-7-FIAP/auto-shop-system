from pathlib import Path
import unittest


WORKFLOW = (
    Path(__file__).resolve().parents[1]
    / ".github"
    / "workflows"
    / "new-relic-hml-canary.yml"
)


class NewRelicCanaryWorkflowTests(unittest.TestCase):
    def test_workflow_is_manual_and_requires_explicit_ingestion_confirmation(self) -> None:
        content = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", content)
        self.assertIn("confirm_hml_ingestion:", content)
        self.assertIn("default: false", content)
        self.assertIn('CONFIRM_HML_INGESTION: ${{ inputs.confirm_hml_ingestion }}', content)
        self.assertIn('[[ "$CONFIRM_HML_INGESTION" == "true" ]]', content)
        self.assertIn("if: github.event_name == 'workflow_dispatch'", content)
        self.assertIn("options: [us]", content)
        self.assertNotIn("options: [us, eu, jp]", content)
        self.assertNotIn("schedule:", content)
        self.assertNotIn("  push:", content)

    def test_workflow_reuses_the_hml_session_gate_without_aws_permissions(self) -> None:
        content = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn('SOURCE_REF: ${{ github.ref }}', content)
        self.assertIn('[[ "$SOURCE_REF" == "refs/heads/develop" ]]', content)
        self.assertIn("environment: hml", content)
        self.assertIn("STAGING_SESSION_ALLOW_ANY_TIME", content)
        self.assertIn("secrets.LIFECYCLE_SESSION_SIGNING_KEY", content)
        self.assertIn("LIFECYCLE_SESSION_TOKEN: ${{ inputs.session_token }}", content)
        self.assertIn("validate_environment_window.py --action operate", content)
        self.assertIn("contents: read", content)
        self.assertNotIn("id-token: write", content)
        self.assertNotIn("aws-actions/configure-aws-credentials", content)

    def test_new_relic_key_is_scoped_to_the_single_ingestion_step(self) -> None:
        content = WORKFLOW.read_text(encoding="utf-8")
        before, step = content.split("- name: Send one synthetic OTLP metric", maxsplit=1)
        self.assertNotIn("NEW_RELIC_LICENSE_KEY", before)
        self.assertIn("NEW_RELIC_LICENSE_KEY: ${{ secrets.NEW_RELIC_LICENSE_KEY }}", step)
        self.assertIn("scripts/observability/new_relic_canary.py", step)


if __name__ == "__main__":
    unittest.main()

