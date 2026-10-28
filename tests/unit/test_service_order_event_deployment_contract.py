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
