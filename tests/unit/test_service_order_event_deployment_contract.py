from pathlib import Path


ROOT = Path(__file__).parents[2]


def test_eventbridge_to_sns_delivery_is_scoped_and_has_a_per_stage_dlq():
    terraform = (ROOT / "infra/aws/service_order_events.tf").read_text(encoding="utf-8")

    assert '"detail-type" = ["ServiceOrderProcessingFailed"]' in terraform
    assert 'event_version = [1]' in terraform
    assert 'actions   = ["events:PutEvents"]' in terraform
    assert "aws_cloudwatch_event_bus.service_order[each.key].arn" in terraform
    assert 'actions   = ["sns:Publish"]' in terraform
    assert 'actions   = ["sqs:SendMessage"]' in terraform
    assert 'variable = "aws:SourceArn"' in terraform
    assert 'variable = "aws:SourceAccount"' in terraform
    assert "aws_sqs_queue.service_order_event_dlq[each.key].arn" in terraform
    assert "maximum_retry_attempts       = 185" in terraform
    assert "sqs_managed_sse_enabled   = true" in terraform
    assert "aws_kms_key.service_order_alerts.arn" in terraform
    assert "kms:EncryptionContext:aws:sns:topicArn" in terraform


def test_irsa_and_ssm_contract_are_stage_specific_and_least_privilege():
    terraform = (ROOT / "infra/aws/service_order_events.tf").read_text(encoding="utf-8")
    upstream = (ROOT / "infra/aws/private_networking.tf").read_text(encoding="utf-8")
    deployment_iam = (ROOT / "infra/aws/github_oidc.tf").read_text(encoding="utf-8")

    assert 'eks_oidc_provider_arn = "eks/oidc-provider-arn"' in upstream
    assert 'variable = "${local.eks_oidc_claim_prefix}:aud"' in terraform
    assert 'variable = "${local.eks_oidc_claim_prefix}:sub"' in terraform
    assert 'system:serviceaccount:${local.service_order_namespaces[each.key]}:auto-shop-backend' in terraform
    assert "events:PutEvents" in terraform
    assert "aws_cloudwatch_event_bus.service_order[each.key].arn" in terraform
    assert '"${trimsuffix(var.upstream_ssm_prefix, "/")}/events/service-order-bus-name"' in terraform
    assert 'events/service-order-publisher-role-arn/${stage}' in terraform
    assert "aws_ssm_parameter.service_order_bus_name" in deployment_iam
    assert "aws_ssm_parameter.service_order_publisher_role_arn" in deployment_iam


def test_kubernetes_deploy_injects_only_the_resolved_bus_and_irsa_role():
    deployment = (ROOT / "k8s/base/app/deployment.yaml").read_text(encoding="utf-8")
    service_account = (ROOT / "k8s/base/foundation/backend-service-account.yaml").read_text(
        encoding="utf-8"
    )
    deploy_script = (ROOT / "k8s/scripts/deploy.sh").read_text(encoding="utf-8")
    staging_workflow = (ROOT / ".github/workflows/cd-staging.yml").read_text(encoding="utf-8")
    production_workflow = (ROOT / ".github/workflows/cd-prod.yml").read_text(encoding="utf-8")
    ci_workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "serviceAccountName: auto-shop-backend" in deployment
    assert "name: auto-shop-backend" in service_account
    assert "__SERVICE_ORDER_PUBLISHER_ROLE_ARN__" in deploy_script
    assert "__SERVICE_ORDER_EVENT_BUS_NAME__" in deploy_script
    assert "service-order-bus-name" in staging_workflow
    assert "service-order-bus-name/prd" in production_workflow
    assert "service-order-publisher-role-arn/hml" in staging_workflow
    assert "service-order-publisher-role-arn/prd" in production_workflow
    assert "SERVICE_ORDER_PUBLISHER_ROLE_ARN" in staging_workflow
    assert "SERVICE_ORDER_PUBLISHER_ROLE_ARN" in production_workflow
    assert "__SERVICE_ORDER_EVENT_BUS_NAME__" in ci_workflow
    assert "__SERVICE_ORDER_PUBLISHER_ROLE_ARN__" in ci_workflow
    assert (
        "if: vars.DEPLOY_STAGING_FRONTEND_ENABLED == 'true'"
        in staging_workflow
    )
    assert (
        "if: vars.DEPLOY_PRODUCTION_FRONTEND_ENABLED == 'true'"
        in production_workflow
    )
    staging_frontend_job = staging_workflow.split("deploy-staging-frontend:", 1)[1].split(
        "deploy-staging-skipped:", 1
    )[0]
    production_frontend_job = production_workflow.split("deploy-production-frontend:", 1)[1].split(
        "deploy-production-skipped:", 1
    )[0]
    assert "needs: deploy-staging" in staging_frontend_job
    assert "needs: deploy-production" in production_frontend_job
    assert "DEPLOY_STAGING_ENABLED == 'true'" not in staging_frontend_job
    assert "DEPLOY_PRODUCTION_ENABLED == 'true'" not in production_frontend_job
    assert "[A-Za-z0-9][A-Za-z0-9_-]{0,99}" in staging_workflow
    assert "[A-Za-z0-9][A-Za-z0-9_-]{0,99}" in production_workflow
    assert "secret:[A-Za-z0-9/_+=.@-]+$" in staging_workflow
    assert "secret:[A-Za-z0-9/_+=.@-]+$" in production_workflow


def test_frontend_ssm_targets_are_validated_before_becoming_workflow_outputs():
    workflow = (ROOT / ".github/workflows/reusable-frontend-deploy.yml").read_text(encoding="utf-8")

    bucket_validation = workflow.index('if [[ ! "${bucket}" =~')
    distribution_validation = workflow.index('if [[ ! "${distribution_id}" =~')
    bucket_output = workflow.index('echo "bucket=${bucket}"')
    distribution_output = workflow.index('echo "distribution_id=${distribution_id}"')

    assert bucket_validation < bucket_output
    assert distribution_validation < distribution_output
    assert "^E[A-Z0-9]{13}$" in workflow


def test_backend_and_frontend_github_deploy_roles_have_separate_permissions():
    terraform = (ROOT / "infra/aws/github_oidc.tf").read_text(encoding="utf-8")
    frontend_workflow = (ROOT / ".github/workflows/reusable-frontend-deploy.yml").read_text(
        encoding="utf-8"
    )

    backend_policy = terraform.split(
        'data "aws_iam_policy_document" "github_deploy_eks"', maxsplit=1
    )[1].split('data "aws_iam_policy_document" "github_frontend_deploy"', maxsplit=1)[0]
    frontend_policy = terraform.split(
        'data "aws_iam_policy_document" "github_frontend_deploy"', maxsplit=1
    )[1].split('resource "aws_iam_role_policy" "github_deploy_eks"', maxsplit=1)[0]

    assert 'actions = ["eks:DescribeCluster"]' in backend_policy
    assert '"s3:PutObject"' not in backend_policy
    assert '"s3:DeleteObject"' not in backend_policy
    assert '"cloudfront:CreateInvalidation"' not in backend_policy
    assert '"s3:PutObject"' in frontend_policy
    assert '"s3:DeleteObject"' in frontend_policy
    assert '"cloudfront:CreateInvalidation"' in frontend_policy
    assert "secrets.AWS_FRONTEND_DEPLOY_ROLE_ARN" in frontend_workflow
