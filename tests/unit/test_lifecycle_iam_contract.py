from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INFRA = ROOT / "infra" / "aws"


def test_deploy_role_trust_uses_only_supported_oidc_claims():
    terraform = (INFRA / "github_oidc.tf").read_text(encoding="utf-8")
    trust = terraform.split('data "aws_iam_policy_document" "github_deploy_assume"', 1)[1].split(
        'resource "aws_iam_role" "github_deploy"', 1
    )[0]
    staging = (ROOT / ".github/workflows/cd-staging.yml").read_text(encoding="utf-8")
    production = (ROOT / ".github/workflows/cd-prod.yml").read_text(encoding="utf-8")

    assert 'token.actions.githubusercontent.com:aud' in trust
    assert 'token.actions.githubusercontent.com:sub' in trust
    assert 'token.actions.githubusercontent.com:ref' not in trust
    assert '"refs/heads/develop"' in staging
    assert '"refs/heads/main"' in production


def test_lifecycle_trusts_use_exact_environment_subjects_and_supported_claims():
    terraform = (INFRA / "lifecycle_iam.tf").read_text(encoding="utf-8")
    assert 'token.actions.githubusercontent.com:aud' in terraform
    assert 'token.actions.githubusercontent.com:sub' in terraform
    assert 'values   = ["${local.github_oidc_subject_prefix}:environment:operations"]' in terraform
    assert 'values   = ["${local.github_oidc_subject_prefix}:environment:hml-lifecycle"]' in terraform
    assert 'repo:Software-Architecture-Group-7-FIAP@279547328/database-infra@1420971567:environment:staging' in terraform
    assert 'repo:Software-Architecture-Group-7-FIAP@279547328/k8s-infra@1431503198:environment:staging' in terraform


def test_cost_reader_trust_keeps_hml_close_and_scopes_start_to_main_workflow():
    terraform = (INFRA / "lifecycle_iam.tf").read_text(encoding="utf-8")
    cost_trust = terraform.split(
        'data "aws_iam_policy_document" "github_lifecycle_cost_reader_assume"', 1
    )[1].split('data "aws_iam_policy_document" "github_lifecycle_cost_reader"', 1)[0]
    cost_role = terraform.split(
        'resource "aws_iam_role" "github_lifecycle_cost_reader"', 1
    )[1].split('resource "aws_iam_role_policy" "github_lifecycle_cost_reader"', 1)[0]
    start_workflow = (ROOT / ".github" / "workflows" / "environment-start.yml").read_text(
        encoding="utf-8"
    )
    stop_workflow = (ROOT / ".github" / "workflows" / "environment-stop.yml").read_text(
        encoding="utf-8"
    )

    trust_statements = cost_trust.split("\n  statement {")[1:]
    assert len(trust_statements) == 2
    close_trust = trust_statements[0].split("\n  }", 1)[0]
    start_trust = trust_statements[1].split("\n  }", 1)[0]
    assert 'values   = ["sts.amazonaws.com"]' in close_trust
    assert 'values   = ["${local.github_oidc_subject_prefix}:environment:hml-lifecycle"]' in close_trust
    assert 'token.actions.githubusercontent.com:workflow' not in close_trust
    assert 'token.actions.githubusercontent.com:ref' not in close_trust
    assert 'token.actions.githubusercontent.com:aud' in start_trust
    assert 'values   = ["sts.amazonaws.com"]' in start_trust
    assert 'token.actions.githubusercontent.com:sub' in start_trust
    assert 'values   = ["${local.github_oidc_subject_prefix}:environment:operations"]' in start_trust
    assert 'variable = "token.actions.githubusercontent.com:workflow"' in start_trust
    assert 'values   = ["Coordinated environment start"]' in start_trust
    assert 'variable = "token.actions.githubusercontent.com:ref"' in start_trust
    assert 'values   = ["refs/heads/main"]' in start_trust
    assert 'variable = "token.actions.githubusercontent.com:environment"' in start_trust
    assert 'values   = ["operations"]' in start_trust
    assert 'permissions_boundary = local.github_deploy_permissions_boundary_arn' in cost_role

    open_job = start_workflow.split("  open:\n", 1)[1].split(
        "\n  alert-prd-opening-failure:", 1
    )[0]
    stop_cost_job = stop_workflow.split("  post-cost-capture:\n", 1)[1].split(
        "\n  alert-close-failure:", 1
    )[0]
    assert "name: Coordinated environment start" in start_workflow
    assert "environment: operations" in open_job
    assert "Configure read-only Cost Explorer identity" in open_job
    assert "environment: hml-lifecycle" in stop_cost_job
    assert "Configure the HML-only Cost Explorer reader" in stop_cost_job


def test_lifecycle_ledger_permissions_have_boundaries_and_nonempty_key_guards():
    terraform = (INFRA / "lifecycle_iam.tf").read_text(encoding="utf-8")
    ledger_access = terraform.split(
        'data "aws_iam_policy_document" "github_lifecycle_ledger_access"', 1
    )[1].split('data "aws_iam_policy_document" "github_lifecycle_consumer_assume"', 1)[0]
    consumer_access = terraform.split(
        'data "aws_iam_policy_document" "github_lifecycle_consumer_access"', 1
    )[1].split('resource "aws_iam_role" "github_lifecycle_ledger"', 1)[0]

    assert 'permissions_boundary = local.github_deploy_permissions_boundary_arn' in terraform
    assert 'ForAllValues:StringLike' in ledger_access
    assert 'test     = "Null"' in ledger_access
    assert 'values   = ["false"]' in ledger_access
    assert 'status-expiry-index' in ledger_access
    assert 'ForAllValues:StringLike' in consumer_access
    assert 'test     = "Null"' in consumer_access
    assert 'values   = ["false"]' in consumer_access


def test_start_role_checks_the_current_hml_and_prd_auth_lambda_contracts():
    terraform = (INFRA / "lifecycle_iam.tf").read_text(encoding="utf-8")
    start_policy = terraform.split(
        'data "aws_iam_policy_document" "github_lifecycle_ledger_access"', 1
    )[1].split('data "aws_iam_policy_document" "github_lifecycle_consumer_assume"', 1)[0]

    assert 'function:lambda-auth-hml' in start_policy
    assert 'function:lambda-auth-prd' in start_policy
    assert 'customer-cpf-auth' not in start_policy


def test_cost_reader_and_alert_roles_are_narrowly_scoped():
    terraform = (INFRA / "lifecycle_iam.tf").read_text(encoding="utf-8")
    cost_policy = terraform.split(
        'data "aws_iam_policy_document" "github_lifecycle_cost_reader"', 1
    )[1].split('resource "aws_iam_role" "github_lifecycle_cost_reader"', 1)[0]
    alert_policy = terraform.split(
        'data "aws_iam_policy_document" "github_lifecycle_alert_publish"', 1
    )[1].split('resource "aws_iam_role" "github_lifecycle_alert_publish"', 1)[0]

    assert 'actions   = ["ce:GetCostAndUsage"]' in cost_policy
    assert 'actions   = ["sns:Publish"]' in alert_policy
    assert 'resources = [aws_sns_topic.lifecycle_alerts[0].arn]' in alert_policy
    assert 'kms_master_key_id = "alias/aws/sns"' in terraform
    assert 'output "github_lifecycle_cost_reader_role_arn"' in terraform
    assert 'output "github_lifecycle_alert_publish_role_arn"' in terraform
