from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_deploy_workflows_read_the_matching_migration_secret_parameter():
    staging = (REPO_ROOT / ".github/workflows/cd-staging.yml").read_text(encoding="utf-8")
    production = (REPO_ROOT / ".github/workflows/cd-prod.yml").read_text(encoding="utf-8")

    assert "/database/secrets/migrations-hml-arn" in staging
    assert "/database/secrets/migrations-prd-arn" in production
    assert "/database/secrets/owner-arn" not in staging
    assert "/database/secrets/owner-arn" not in production


def test_application_migration_identity_attaches_environment_specific_read_policies():
    networking = (REPO_ROOT / "infra/aws/private_networking.tf").read_text(encoding="utf-8")
    identity = (REPO_ROOT / "infra/aws/migration_identity.tf").read_text(encoding="utf-8")

    assert "database/iam/migrations-${each.key}-read-policy-arn" in networking
    assert "database/secrets/migrations-${each.key}-arn" in networking
    assert "data.aws_ssm_parameter.migration_secret_read_policy_arn[local.migration_database_stages[each.key]].value" in identity
    assert "owner-read-policy-arn" not in networking


def test_deployment_role_can_read_only_the_secret_arn_for_its_stage():
    oidc = (REPO_ROOT / "infra/aws/github_oidc.tf").read_text(encoding="utf-8")

    assert "data.aws_ssm_parameter.migration_secret_arn[local.github_environment_api_stage[each.key]].arn" in oidc
    assert "migration_owner_secret_arn" not in oidc
