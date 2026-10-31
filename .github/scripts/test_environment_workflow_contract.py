import re
import unittest
from pathlib import Path


WORKFLOWS = Path(__file__).resolve().parents[1] / "workflows"


class EnvironmentWorkflowContractTests(unittest.TestCase):
    def read(self, name: str) -> str:
        return (WORKFLOWS / name).read_text(encoding="utf-8")

    def test_all_lifecycle_workflows_are_disabled_by_default(self) -> None:
        start = self.read("environment-start.yml")
        self.assertIn("ENVIRONMENT_SCHEDULE_ENABLED || 'false'", start)
        self.assertIn("STAGING_ACTIVE || 'false'", start)
        self.assertIn("STAGING_SESSION_AUTHORIZED || 'false'", start)

        for name in ("environment-health.yml", "environment-stop.yml"):
            with self.subTest(name=name):
                content = self.read(name)
                self.assertRegex(
                    content,
                    re.compile(r"vars\.ENVIRONMENT_SCHEDULE_ENABLED\s*==\s*'true'"),
                )
                if name == "environment-health.yml":
                    self.assertIn("vars.PRD_LIFECYCLE_AUTOMATION_READY == 'true'", content)
                    self.assertIn("vars.PRD_COST_EXCEPTION_APPROVED == 'true'", content)

    def test_start_and_stop_share_non_cancelling_concurrency(self) -> None:
        for name in ("environment-start.yml", "environment-stop.yml"):
            with self.subTest(name=name):
                content = self.read(name)
                self.assertIn("group: environment-lifecycle", content)
                self.assertIn("cancel-in-progress: false", content)

    def test_every_aws_workflow_checks_account_and_region(self) -> None:
        for name in (
            "environment-start.yml",
            "environment-health.yml",
            "environment-stop.yml",
        ):
            with self.subTest(name=name):
                content = self.read(name)
                self.assertIn("EXPECTED_AWS_ACCOUNT_ID", content)
                self.assertIn('"us-east-1"', content)
                self.assertTrue(
                    "aws sts get-caller-identity" in content
                    or '--expected-account-id "$EXPECTED_AWS_ACCOUNT_ID"' in content
                )

    def test_health_uses_public_endpoints_without_storing_response_bodies(self) -> None:
        content = self.read("environment-health.yml")
        self.assertIn("/health/live", content)
        self.assertIn("/health/ready", content)
        self.assertIn("/.well-known/jwks.json", content)
        self.assertIn("--output /dev/null", content)
        self.assertIn("health-summary.json", content)
        self.assertIn("aws sns publish", content)
        self.assertNotIn("Authorization:", content)

    def test_no_2130_deploy_block_is_introduced(self) -> None:
        for name in (
            "environment-start.yml",
            "environment-health.yml",
            "environment-stop.yml",
        ):
            with self.subTest(name=name):
                self.assertNotIn("21:30", self.read(name))

    def test_staging_and_production_deployments_use_separate_migration_secrets(self) -> None:
        staging = (WORKFLOWS / "cd-staging.yml").read_text(encoding="utf-8")
        production = (WORKFLOWS / "cd-prod.yml").read_text(encoding="utf-8")

        self.assertIn("/database/secrets/migrations-hml-arn", staging)
        self.assertIn("/database/secrets/migrations-prd-arn", production)
        self.assertNotIn("/database/secrets/owner-arn", staging)
        self.assertNotIn("/database/secrets/owner-arn", production)

    def test_deploy_workflows_use_environment_scoped_oidc_roles_and_branches(self) -> None:
        staging = (WORKFLOWS / "cd-staging.yml").read_text(encoding="utf-8")
        production = (WORKFLOWS / "cd-prod.yml").read_text(encoding="utf-8")
        frontend = self.read("reusable-frontend-deploy.yml")

        self.assertIn("environment: hml", staging)
        self.assertIn('SOURCE_REF" == "refs/heads/develop"', staging)
        self.assertIn("vars.AWS_DEPLOY_ROLE_ARN_HML", staging)
        self.assertNotIn("secrets.AWS_DEPLOY_ROLE_ARN", staging)

        self.assertIn("environment: prd", production)
        self.assertIn('SOURCE_REF" == "refs/heads/main"', production)
        self.assertIn("vars.AWS_DEPLOY_ROLE_ARN_PRD", production)
        self.assertNotIn("secrets.AWS_DEPLOY_ROLE_ARN", production)

        self.assertIn("AWS_FRONTEND_DEPLOY_ROLE_ARN_HML", frontend)
        self.assertIn("AWS_FRONTEND_DEPLOY_ROLE_ARN_PRD", frontend)
        self.assertNotIn("secrets.AWS_FRONTEND_DEPLOY_ROLE_ARN", frontend)
        self.assertIn('hml) expected_ref="refs/heads/develop"', frontend)
        self.assertIn('prd) expected_ref="refs/heads/main"', frontend)


if __name__ == "__main__":
    unittest.main()
