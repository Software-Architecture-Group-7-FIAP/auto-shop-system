locals {
  service_order_environments = {
    hml = "staging"
    prd = "production"
  }

  service_order_namespaces = {
    hml = "auto-shop-hml"
    prd = "auto-shop-prd"
  }

  service_order_bus_parameter_names = {
    hml = "${trimsuffix(var.upstream_ssm_prefix, "/")}/events/service-order-bus-name"
    prd = "${trimsuffix(var.upstream_ssm_prefix, "/")}/events/service-order-bus-name/prd"
  }

  service_order_publisher_role_parameter_names = {
    for stage in local.api_stages : stage => "${trimsuffix(var.upstream_ssm_prefix, "/")}/events/service-order-publisher-role-arn/${stage}"
  }

  eks_oidc_claim_prefix = trimprefix(
    data.aws_ssm_parameter.upstream["eks_oidc_provider_arn"].value,
    "arn:aws:iam::${data.aws_caller_identity.current.account_id}:oidc-provider/",
  )
}

resource "aws_cloudwatch_event_bus" "service_order" {
  for_each = local.api_stages

  name = "${var.project_name}-service-orders-${local.service_order_environments[each.key]}"

  tags = merge(local.common_tags, {
    Name      = "${var.project_name}-service-orders-${local.service_order_environments[each.key]}"
    Component = "service-order-events"
  })
}

data "aws_iam_policy_document" "service_order_alerts_key" {
  statement {
    sid    = "EnableAccountKeyAdministration"
    effect = "Allow"

    principals {
      type        = "AWS"
      identifiers = ["arn:${data.aws_partition.current.partition}:iam::${data.aws_caller_identity.current.account_id}:root"]
    }

    actions   = ["kms:*"]
    resources = ["*"]
  }

  statement {
    sid    = "AllowSNSAndDeliveryServicesForThisTopic"
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["events.amazonaws.com", "cloudwatch.amazonaws.com", "sns.amazonaws.com"]
    }

    actions   = ["kms:Decrypt", "kms:GenerateDataKey*"]
    resources = ["*"]

    condition {
      test     = "StringEquals"
      variable = "kms:EncryptionContext:aws:sns:topicArn"
      values   = [local.service_order_alert_topic_arn]
    }
  }
}

resource "aws_kms_key" "service_order_alerts" {
  description             = "Encrypt service-order failure alert messages in SNS."
  enable_key_rotation     = true
  deletion_window_in_days = 7
  policy                  = data.aws_iam_policy_document.service_order_alerts_key.json

  tags = merge(local.common_tags, {
    Name      = "${local.name_prefix}-service-order-alerts"
    Component = "service-order-events"
  })
}

resource "aws_kms_alias" "service_order_alerts" {
  name          = "alias/${local.name_prefix}/service-order-alerts"
  target_key_id = aws_kms_key.service_order_alerts.key_id
}

resource "aws_sns_topic" "service_order_alerts" {
  name              = "${local.name_prefix}-service-order-alerts"
  kms_master_key_id = aws_kms_key.service_order_alerts.arn

  tags = merge(local.common_tags, {
    Name      = "${local.name_prefix}-service-order-alerts"
    Component = "service-order-events"
  })
}

resource "aws_sns_topic_subscription" "service_order_alert_email" {
  count = trimspace(var.service_order_alert_email) == "" ? 0 : 1

  topic_arn = aws_sns_topic.service_order_alerts.arn
  protocol  = "email"
  endpoint  = trimspace(var.service_order_alert_email)
}

resource "aws_sqs_queue" "service_order_event_dlq" {
  for_each = local.api_stages

  name                      = "${local.name_prefix}-service-order-${each.key}-dlq"
  message_retention_seconds = 1209600
  sqs_managed_sse_enabled   = true

  tags = merge(local.common_tags, {
    Name      = "${local.name_prefix}-service-order-${each.key}-dlq"
    Component = "service-order-events"
  })
}

resource "aws_cloudwatch_event_rule" "service_order_failed" {
  for_each = local.api_stages

  name           = "${local.name_prefix}-service-order-failed-${each.key}"
  description    = "Route version 1 service-order processing failures to operational email alerts."
  event_bus_name = aws_cloudwatch_event_bus.service_order[each.key].name
  event_pattern = jsonencode({
    source        = ["auto-shop.service-orders"]
    "detail-type" = ["ServiceOrderProcessingFailed"]
    detail = {
      event_version = [1]
    }
  })

  tags = merge(local.common_tags, {
    Name      = "${local.name_prefix}-service-order-failed-${each.key}"
    Component = "service-order-events"
  })
}

resource "aws_cloudwatch_event_target" "service_order_alerts" {
  for_each = local.api_stages

  event_bus_name = aws_cloudwatch_event_bus.service_order[each.key].name
  rule           = aws_cloudwatch_event_rule.service_order_failed[each.key].name
  target_id      = "service-order-alert-email"
  arn            = aws_sns_topic.service_order_alerts.arn

  dead_letter_config {
    arn = aws_sqs_queue.service_order_event_dlq[each.key].arn
  }

  retry_policy {
    maximum_event_age_in_seconds = 86400
    maximum_retry_attempts       = 185
  }

  input_transformer {
    input_paths = {
      occurred_at      = "$.detail.occurred_at"
      event_id         = "$.detail.event_id"
      request_id       = "$.detail.request_id"
      service_order_id = "$.detail.service_order_id"
    }

    input_template = "\"Service-order processing failed in ${each.key}. Event ID <event_id>; service-order ID <service_order_id>; request ID <request_id>; occurred at <occurred_at>. Check the application logs using the request ID.\""
  }

  depends_on = [
    aws_sns_topic_policy.service_order_events,
    aws_sqs_queue_policy.service_order_event_dlq,
  ]
}

resource "aws_cloudwatch_metric_alarm" "service_order_event_dlq_visible" {
  for_each = local.api_stages

  alarm_name          = "${local.name_prefix}-service-order-${each.key}-dlq-not-empty"
  alarm_description   = "A service-order failure event could not be delivered to SNS and is waiting in the EventBridge DLQ."
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  datapoints_to_alarm = 1
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 60
  statistic           = "Maximum"
  threshold           = 1
  treat_missing_data  = "notBreaching"

  dimensions = {
    QueueName = aws_sqs_queue.service_order_event_dlq[each.key].name
  }

  alarm_actions = [aws_sns_topic.service_order_alerts.arn]

  tags = merge(local.common_tags, {
    Name      = "${local.name_prefix}-service-order-${each.key}-dlq-not-empty"
    Component = "service-order-events"
  })
}

data "aws_iam_policy_document" "service_order_sns_events" {
  statement {
    sid    = "AllowEventBridgeFromServiceOrderRules"
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["events.amazonaws.com"]
    }

    actions   = ["sns:Publish"]
    resources = [aws_sns_topic.service_order_alerts.arn]

    condition {
      test     = "ArnEquals"
      variable = "aws:SourceArn"
      values   = [for rule in aws_cloudwatch_event_rule.service_order_failed : rule.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }
  }

  statement {
    sid    = "AllowCloudWatchFromServiceOrderDlqAlarms"
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["cloudwatch.amazonaws.com"]
    }

    actions   = ["sns:Publish"]
    resources = [aws_sns_topic.service_order_alerts.arn]

    condition {
      test     = "ArnEquals"
      variable = "aws:SourceArn"
      values   = [for alarm in aws_cloudwatch_metric_alarm.service_order_event_dlq_visible : alarm.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }
  }
}

resource "aws_sns_topic_policy" "service_order_events" {
  arn    = aws_sns_topic.service_order_alerts.arn
  policy = data.aws_iam_policy_document.service_order_sns_events.json
}

data "aws_iam_policy_document" "service_order_event_dlq" {
  for_each = local.api_stages

  statement {
    sid    = "AllowEventBridgeFromMatchingRule"
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["events.amazonaws.com"]
    }

    actions   = ["sqs:SendMessage"]
    resources = [aws_sqs_queue.service_order_event_dlq[each.key].arn]

    condition {
      test     = "ArnEquals"
      variable = "aws:SourceArn"
      values   = [aws_cloudwatch_event_rule.service_order_failed[each.key].arn]
    }

    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }
  }
}

resource "aws_sqs_queue_policy" "service_order_event_dlq" {
  for_each = local.api_stages

  queue_url = aws_sqs_queue.service_order_event_dlq[each.key].url
  policy    = data.aws_iam_policy_document.service_order_event_dlq[each.key].json
}

data "aws_iam_policy_document" "service_order_publisher_assume" {
  for_each = local.api_stages

  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [data.aws_ssm_parameter.upstream["eks_oidc_provider_arn"].value]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.eks_oidc_claim_prefix}:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.eks_oidc_claim_prefix}:sub"
      values   = ["system:serviceaccount:${local.service_order_namespaces[each.key]}:auto-shop-backend"]
    }
  }
}

resource "aws_iam_role" "service_order_publisher" {
  for_each = local.api_stages

  name               = "${local.name_prefix}-${each.key}-service-order-events-publisher"
  assume_role_policy = data.aws_iam_policy_document.service_order_publisher_assume[each.key].json

  tags = merge(local.common_tags, {
    Name      = "${local.name_prefix}-${each.key}-service-order-events-publisher"
    Component = "service-order-events"
  })
}

data "aws_iam_policy_document" "service_order_publisher" {
  for_each = local.api_stages

  statement {
    sid       = "PublishServiceOrderFailureEvents"
    effect    = "Allow"
    actions   = ["events:PutEvents"]
    resources = [aws_cloudwatch_event_bus.service_order[each.key].arn]
  }
}

resource "aws_iam_role_policy" "service_order_publisher" {
  for_each = local.api_stages

  name   = "publish-service-order-events"
  role   = aws_iam_role.service_order_publisher[each.key].id
  policy = data.aws_iam_policy_document.service_order_publisher[each.key].json
}

resource "aws_ssm_parameter" "service_order_bus_name" {
  for_each = local.api_stages

  name  = local.service_order_bus_parameter_names[each.key]
  type  = "String"
  value = aws_cloudwatch_event_bus.service_order[each.key].name

  tags = merge(local.common_tags, {
    Name      = local.service_order_bus_parameter_names[each.key]
    Component = "service-order-events"
  })
}

resource "aws_ssm_parameter" "service_order_publisher_role_arn" {
  for_each = local.api_stages

  name  = local.service_order_publisher_role_parameter_names[each.key]
  type  = "String"
  value = aws_iam_role.service_order_publisher[each.key].arn

  tags = merge(local.common_tags, {
    Name      = local.service_order_publisher_role_parameter_names[each.key]
    Component = "service-order-events"
  })
}

variable "service_order_alert_email" {
  description = "Email endpoint for SNS failure alerts. Leave empty until an address is chosen and available to confirm the subscription."
  type        = string
  default     = ""

  validation {
    condition = trimspace(var.service_order_alert_email) == "" || can(regex(
      "^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$",
      trimspace(var.service_order_alert_email),
    ))
    error_message = "service_order_alert_email must be empty or a valid email address."
  }
}

output "service_order_event_bus_names" {
  description = "EventBridge bus names by API stage (hml and prd)."
  value       = { for stage, bus in aws_cloudwatch_event_bus.service_order : stage => bus.name }
}

output "service_order_publisher_role_arns" {
  description = "IRSA publisher role ARNs by Kubernetes stage (hml and prd)."
  value       = { for stage, role in aws_iam_role.service_order_publisher : stage => role.arn }
}

output "service_order_alert_topic_arn" {
  description = "SNS topic ARN receiving service-order failure events."
  value       = aws_sns_topic.service_order_alerts.arn
}

output "service_order_alert_kms_key_arn" {
  description = "Customer-managed KMS key used to encrypt service-order SNS alerts."
  value       = aws_kms_key.service_order_alerts.arn
}

output "service_order_event_dlq_arns" {
  description = "EventBridge target dead-letter queue ARNs by API stage."
  value       = { for stage, queue in aws_sqs_queue.service_order_event_dlq : stage => queue.arn }
}

output "service_order_event_dlq_alarm_arns" {
  description = "CloudWatch alarm ARNs for non-empty EventBridge target DLQs, by API stage."
  value       = { for stage, alarm in aws_cloudwatch_metric_alarm.service_order_event_dlq_visible : stage => alarm.arn }
}
