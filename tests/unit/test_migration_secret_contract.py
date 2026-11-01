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

    assert "local.github_deploy_parameter_arns[each.key]" in oidc
    assert "database/secrets/migrations-" in oidc
    assert "data.aws_ssm_parameter.migration_secret_arn" not in oidc
    assert 'values   = ["${local.github_oidc_subject_prefix}:environment:${local.github_environment_name[each.key]}"]' in oidc
    assert 'default     = "279547328"' in oidc
    assert 'default     = "1221936756"' in oidc
    assert "repo:${var.github_repository}:environment:" not in oidc
    assert "migration_owner_secret_arn" not in oidc


def test_oidc_role_environment_subjects_match_deployment_workflows():
    staging = (REPO_ROOT / ".github/workflows/cd-staging.yml").read_text(encoding="utf-8")
    production = (REPO_ROOT / ".github/workflows/cd-prod.yml").read_text(encoding="utf-8")
    oidc = (REPO_ROOT / "infra/aws/github_oidc.tf").read_text(encoding="utf-8")
    infra_readme = (REPO_ROOT / "infra/aws/README.md").read_text(encoding="utf-8")
    deployment_readme = (REPO_ROOT / "docs/deployment.md").read_text(encoding="utf-8")

    assert "environment: hml" in staging
    assert "environment: prd" in production
    assert 'staging    = "hml"' in oidc
    assert 'production = "prd"' in oidc
    assert 'values   = ["${local.github_oidc_subject_prefix}:environment:${local.github_environment_name[each.key]}"]' in oidc
    assert 'toset(["staging", "production"])' in oidc
    assert "| `hml` | `hml` |" in infra_readme
    assert "| `prd` | `prd` |" in infra_readme
    assert "| push ou `workflow_dispatch` em `develop` | `hml` |" in deployment_readme
    assert "| push ou `workflow_dispatch` em `main` | `prd` |" in deployment_readme


def test_alembic_preserves_percent_encoded_passwords_and_deploy_logs_redact_driver_urls():
    alembic_env = (REPO_ROOT / "alembic/env.py").read_text(encoding="utf-8")
    deploy_script = (REPO_ROOT / "k8s/scripts/deploy.sh").read_text(encoding="utf-8")

    assert 'settings.database_url.replace("%", "%%")' in alembic_env
    assert r"(postgres(ql)?(\+[^:/?#[:space:]]+)?://)" in deploy_script
