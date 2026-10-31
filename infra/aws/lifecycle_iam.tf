resource "aws_dynamodb_table" "lifecycle_sessions" {
  name                        = "${local.name_prefix}-lifecycle-sessions"
  billing_mode                = "PAY_PER_REQUEST"
  hash_key                    = "session_id"
  range_key                   = "record_key"
  deletion_protection_enabled = true

  attribute {
    name = "session_id"
    type = "S"
  }

  attribute {
    name = "record_key"
    type = "S"
  }

  attribute {
    name = "status"
    type = "S"
  }

  attribute {
    name = "expires_at"
    type = "N"
  }

  global_secondary_index {
    name            = "status-expiry-index"
    hash_key        = "status"
    range_key       = "expires_at"
    projection_type = "ALL"
  }

  ttl {
    attribute_name = "ttl_epoch_seconds"
    enabled        = true
  }

  server_side_encryption {
    enabled = true
  }

  point_in_time_recovery {
    enabled                 = true
    recovery_period_in_days = 35
  }

  tags = merge(local.common_tags, {
    Component = "lifecycle-session-ledger"
  })
}

locals {
  github_lifecycle_ledger_roles = {
    cleanup = {
      description = "Short-lived OIDC access to the lifecycle ledger for the exact Expired lifecycle session cleanup workflow."
    }
    health = {
      description = "Short-lived OIDC access to the lifecycle ledger for the exact Environment public health workflow."
    }
    start = {
      description = "Short-lived OIDC access to the lifecycle ledger for the exact Coordinated environment start workflow."
    }
    stop = {
      description = "Short-lived OIDC access to the lifecycle ledger for the exact Coordinated environment stop workflow."
    }
  }

  github_lifecycle_consumer_roles = {
    "app-hml" = {
      subject     = "${local.github_oidc_subject_prefix}:environment:hml"
      description = "Read and atomically claim lifecycle dispatch authorizations for the exact CD Staging workflow."
    }
    "app-prd" = {
      subject     = "${local.github_oidc_subject_prefix}:environment:prd"
      description = "Read and atomically claim lifecycle dispatch authorizations for the exact CD Production workflow."
    }
    "database-apply" = {
      subject     = "repo:Software-Architecture-Group-7-FIAP@279547328/database-infra@1420971567:environment:staging"
      description = "Read and atomically claim lifecycle dispatch authorizations for the exact Apply database staging workflow."
    }
    "database-destroy" = {
      subject     = "repo:Software-Architecture-Group-7-FIAP@279547328/database-infra@1420971567:environment:staging"
      description = "Read and atomically claim lifecycle dispatch authorizations for the exact Destroy database staging workflow."
    }
    "k8s-apply" = {
      subject     = "repo:Software-Architecture-Group-7-FIAP@279547328/k8s-infra@1431503198:environment:staging"
      description = "Read and atomically claim lifecycle dispatch authorizations for the exact Apply workflow."
    }
    "k8s-ci" = {
      subject     = "repo:Software-Architecture-Group-7-FIAP@279547328/k8s-infra@1431503198:environment:staging"
      description = "Read and atomically claim lifecycle dispatch authorizations for the exact CI workflow."
    }
    "k8s-destroy" = {
      subject     = "repo:Software-Architecture-Group-7-FIAP@279547328/k8s-infra@1431503198:environment:staging"
      description = "Read and atomically claim lifecycle dispatch authorizations for the exact Destroy workflow."
    }
    "k8s-orphan-audit" = {
      subject     = "repo:Software-Architecture-Group-7-FIAP@279547328/k8s-infra@1431503198:environment:staging"
      description = "Read and atomically claim lifecycle dispatch authorizations for the exact Orphan Audit workflow."
    }
  }
}

data "aws_iam_policy_document" "github_lifecycle_ledger_assume" {
  for_each = var.enable_github_oidc ? local.github_lifecycle_ledger_roles : {}

  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [data.aws_iam_openid_connect_provider.github.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["${local.github_oidc_subject_prefix}:environment:operations"]
    }
  }
}

data "aws_iam_policy_document" "github_lifecycle_ledger_access" {
  for_each = var.enable_github_oidc ? local.github_lifecycle_ledger_roles : {}

  statement {
    sid       = "AccessLifecycleSessionRows"
    actions   = each.key == "health" ? ["dynamodb:UpdateItem", "dynamodb:GetItem"] : ["dynamodb:UpdateItem", "dynamodb:PutItem", "dynamodb:GetItem"]
    resources = [aws_dynamodb_table.lifecycle_sessions.arn]

    condition {
      test     = "ForAllValues:StringLike"
      variable = "dynamodb:LeadingKeys"
      values   = ["hml-*", "prd-*"]
    }

    condition {
      test     = "Null"
      variable = "dynamodb:LeadingKeys"
      values   = ["false"]
    }
  }

  dynamic "statement" {
    for_each = each.key == "start" ? [1] : []

    content {
      sid       = "DescribeLifecycleSessionTable"
      actions   = ["dynamodb:DescribeTable"]
      resources = [aws_dynamodb_table.lifecycle_sessions.arn]
    }
  }

  dynamic "statement" {
    for_each = each.key == "cleanup" ? [1] : []

    content {
      sid       = "QueryExpiredLifecycleSessions"
      actions   = ["dynamodb:Query"]
      resources = ["${aws_dynamodb_table.lifecycle_sessions.arn}/index/status-expiry-index"]

      condition {
        test     = "ForAllValues:StringEquals"
        variable = "dynamodb:LeadingKeys"
        values   = ["active", "closing"]
      }

      condition {
        test     = "Null"
        variable = "dynamodb:LeadingKeys"
        values   = ["false"]
      }
    }
  }

  dynamic "statement" {
    for_each = each.key == "start" ? [1] : []

    content {
      sid     = "ReadNetworkAndAuthContracts"
      actions = ["ssm:GetParameters"]
      resources = [
        "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter/auto-shop/staging/network/workload-private-subnet-ids",
        "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter/auto-shop/staging/network/vpc-id",
        "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter/auto-shop/staging/network/lambda-security-group-id",
        "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter/auto-shop/staging/auth/customer-token/function-arn/hml",
        "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter/auto-shop/staging/auth/customer-token/function-arn/prd",
      ]
    }
  }

  dynamic "statement" {
    for_each = each.key == "start" ? [1] : []

    content {
      sid     = "VerifyPersistentCustomerAuthFunctions"
      actions = ["lambda:GetFunctionConfiguration"]
      resources = [
        "arn:aws:lambda:${var.aws_region}:${data.aws_caller_identity.current.account_id}:function:lambda-auth-hml",
        "arn:aws:lambda:${var.aws_region}:${data.aws_caller_identity.current.account_id}:function:lambda-auth-prd",
      ]
    }
  }
}

data "aws_iam_policy_document" "github_lifecycle_consumer_assume" {
  for_each = var.enable_github_oidc ? local.github_lifecycle_consumer_roles : {}

  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [data.aws_iam_openid_connect_provider.github.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = [each.value.subject]
    }
  }
}

data "aws_iam_policy_document" "github_lifecycle_consumer_access" {
  for_each = var.enable_github_oidc ? local.github_lifecycle_consumer_roles : {}

  statement {
    sid       = "ReadAndClaimLifecycleDispatch"
    actions   = ["dynamodb:GetItem", "dynamodb:UpdateItem"]
    resources = [aws_dynamodb_table.lifecycle_sessions.arn]

    condition {
      test     = "ForAllValues:StringLike"
      variable = "dynamodb:LeadingKeys"
      values   = ["hml-*", "prd-*"]
    }

    condition {
      test     = "Null"
      variable = "dynamodb:LeadingKeys"
      values   = ["false"]
    }
  }
}

resource "aws_iam_role" "github_lifecycle_ledger" {
  for_each = var.enable_github_oidc ? local.github_lifecycle_ledger_roles : {}

  name                 = "${local.name_prefix}-github-lifecycle-${each.key}"
  path                 = "/auto-shop/"
  description          = each.value.description
  max_session_duration = 3600
  assume_role_policy   = data.aws_iam_policy_document.github_lifecycle_ledger_assume[each.key].json
  permissions_boundary = local.github_deploy_permissions_boundary_arn
  tags                 = local.common_tags
}

resource "aws_iam_role_policy" "github_lifecycle_ledger" {
  for_each = var.enable_github_oidc ? local.github_lifecycle_ledger_roles : {}

  name   = "lifecycle-ledger-${each.key}"
  role   = aws_iam_role.github_lifecycle_ledger[each.key].id
  policy = data.aws_iam_policy_document.github_lifecycle_ledger_access[each.key].json
}

resource "aws_iam_role" "github_lifecycle_consumer" {
  for_each = var.enable_github_oidc ? local.github_lifecycle_consumer_roles : {}

  name                 = "${local.name_prefix}-github-lifecycle-consumer-${each.key}"
  path                 = "/auto-shop/"
  description          = each.value.description
  max_session_duration = 3600
  assume_role_policy   = data.aws_iam_policy_document.github_lifecycle_consumer_assume[each.key].json
  permissions_boundary = local.github_deploy_permissions_boundary_arn
  tags                 = local.common_tags
}

resource "aws_iam_role_policy" "github_lifecycle_consumer" {
  for_each = var.enable_github_oidc ? local.github_lifecycle_consumer_roles : {}

  name   = "lifecycle-ledger-consumer-${each.key}"
  role   = aws_iam_role.github_lifecycle_consumer[each.key].id
  policy = data.aws_iam_policy_document.github_lifecycle_consumer_access[each.key].json
}

resource "aws_sns_topic" "lifecycle_alerts" {
  count = var.enable_github_oidc ? 1 : 0

  name              = "${local.name_prefix}-lifecycle-alerts"
  kms_master_key_id = "alias/aws/sns"
  tags = merge(local.common_tags, {
    Component = "lifecycle-alerts"
  })
}

data "aws_iam_policy_document" "github_lifecycle_cost_reader_assume" {
  count = var.enable_github_oidc ? 1 : 0

  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [data.aws_iam_openid_connect_provider.github.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["${local.github_oidc_subject_prefix}:environment:operations"]
    }
  }
}

data "aws_iam_policy_document" "github_lifecycle_cost_reader" {
  count = var.enable_github_oidc ? 1 : 0

  statement {
    sid       = "ReadCostAndUsageOnly"
    actions   = ["ce:GetCostAndUsage"]
    resources = ["*"]
  }
}

resource "aws_iam_role" "github_lifecycle_cost_reader" {
  count = var.enable_github_oidc ? 1 : 0

  name                 = "${local.name_prefix}-github-cost-reader"
  path                 = "/auto-shop/"
  description          = "Read-only Cost Explorer access for the guarded HML lifecycle cost preflight."
  max_session_duration = 3600
  assume_role_policy   = data.aws_iam_policy_document.github_lifecycle_cost_reader_assume[0].json
  permissions_boundary = local.github_deploy_permissions_boundary_arn
  tags                 = local.common_tags
}

resource "aws_iam_role_policy" "github_lifecycle_cost_reader" {
  count = var.enable_github_oidc ? 1 : 0

  name   = "lifecycle-cost-read-only"
  role   = aws_iam_role.github_lifecycle_cost_reader[0].id
  policy = data.aws_iam_policy_document.github_lifecycle_cost_reader[0].json
}

data "aws_iam_policy_document" "github_lifecycle_alert_publish_assume" {
  count = var.enable_github_oidc ? 1 : 0

  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [data.aws_iam_openid_connect_provider.github.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["${local.github_oidc_subject_prefix}:environment:operations"]
    }
  }
}

data "aws_iam_policy_document" "github_lifecycle_alert_publish" {
  count = var.enable_github_oidc ? 1 : 0

  statement {
    sid       = "PublishLifecycleAlertsOnly"
    actions   = ["sns:Publish"]
    resources = [aws_sns_topic.lifecycle_alerts[0].arn]
  }
}

resource "aws_iam_role" "github_lifecycle_alert_publish" {
  count = var.enable_github_oidc ? 1 : 0

  name                 = "${local.name_prefix}-github-lifecycle-alert-publish"
  path                 = "/auto-shop/"
  description          = "Publish lifecycle teardown alerts to the lifecycle alert topic."
  max_session_duration = 3600
  assume_role_policy   = data.aws_iam_policy_document.github_lifecycle_alert_publish_assume[0].json
  permissions_boundary = local.github_deploy_permissions_boundary_arn
  tags                 = local.common_tags
}

resource "aws_iam_role_policy" "github_lifecycle_alert_publish" {
  count = var.enable_github_oidc ? 1 : 0

  name   = "lifecycle-alert-publish"
  role   = aws_iam_role.github_lifecycle_alert_publish[0].id
  policy = data.aws_iam_policy_document.github_lifecycle_alert_publish[0].json
}

output "github_lifecycle_cost_reader_role_arn" {
  description = "Cost Explorer read-only role for guarded HML lifecycle preflight."
  value       = var.enable_github_oidc ? aws_iam_role.github_lifecycle_cost_reader[0].arn : null
}

output "github_lifecycle_alert_publish_role_arn" {
  description = "SNS publish role for lifecycle teardown alerts."
  value       = var.enable_github_oidc ? aws_iam_role.github_lifecycle_alert_publish[0].arn : null
}

output "lifecycle_alert_topic_arn" {
  description = "Encrypted SNS topic for lifecycle teardown alerts; no subscription is created here."
  value       = var.enable_github_oidc ? aws_sns_topic.lifecycle_alerts[0].arn : null
}
