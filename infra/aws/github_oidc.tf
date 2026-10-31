# GitHub Actions OIDC roles for backend, frontend, and lifecycle auth preflight (issue #90).
# Apply once per AWS account; map role ARNs to the documented GitHub Environment variables.

variable "enable_github_oidc" {
  description = "Create GitHub OIDC provider and deploy roles."
  type        = bool
  default     = false
}

variable "github_repository" {
  description = "GitHub repo in org/name form allowed to assume deploy roles."
  type        = string
  default     = "Software-Architecture-Group-7-FIAP/auto-shop-system"

  validation {
    condition     = length(split("/", var.github_repository)) == 2
    error_message = "github_repository must use org/name form."
  }
}

variable "github_repository_owner_id" {
  description = "Immutable GitHub organization ID used in the Actions OIDC subject."
  type        = string
  default     = "279547328"
}

variable "github_repository_id" {
  description = "Immutable GitHub repository ID used in the Actions OIDC subject."
  type        = string
  default     = "1221936756"
}

variable "auth_lambda_function_name" {
  description = "Base function name published by lambda-auth; environment suffixes hml and prd are appended."
  type        = string
  default     = "lambda-auth"

  validation {
    condition     = can(regex("^[A-Za-z0-9_-]{1,46}$", var.auth_lambda_function_name))
    error_message = "auth_lambda_function_name must use 1 to 46 letters, digits, hyphens, or underscores."
  }
}

variable "github_oidc_thumbprint" {
  description = "GitHub Actions OIDC root CA thumbprint (default valid for github.com)."
  type        = string
  default     = "6938fd4d98bab03faadb97b34396831e3780aea1"
}

locals {
  github_oidc_subject_prefix = "repo:${split("/", var.github_repository)[0]}@${var.github_repository_owner_id}/${split("/", var.github_repository)[1]}@${var.github_repository_id}"
  github_environment_api_stage = {
    staging    = "hml"
    production = "prd"
  }
  github_environment_name = {
    staging    = "hml"
    production = "prd"
  }
  github_environment_branch = {
    staging    = "refs/heads/develop"
    production = "refs/heads/main"
  }
}

resource "aws_iam_openid_connect_provider" "github" {
  count = var.enable_github_oidc ? 1 : 0

  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = [var.github_oidc_thumbprint]
}

data "aws_iam_policy_document" "github_deploy_assume" {
  for_each = var.enable_github_oidc ? toset(["staging", "production"]) : toset([])

  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github[0].arn]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["${local.github_oidc_subject_prefix}:environment:${local.github_environment_name[each.key]}"]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:ref"
      values   = [local.github_environment_branch[each.key]]
    }
  }
}

resource "aws_iam_role" "github_deploy" {
  for_each = var.enable_github_oidc ? toset(["staging", "production"]) : toset([])

  name               = "${local.name_prefix}-github-${each.key}"
  assume_role_policy = data.aws_iam_policy_document.github_deploy_assume[each.key].json
}

resource "aws_iam_role" "github_frontend_deploy" {
  for_each = var.enable_github_oidc ? toset(["staging", "production"]) : toset([])

  name               = "${local.name_prefix}-github-${each.key}-frontend"
  assume_role_policy = data.aws_iam_policy_document.github_deploy_assume[each.key].json
}

data "aws_iam_policy_document" "github_deploy_eks" {
  for_each = var.enable_github_oidc ? toset(["staging", "production"]) : toset([])

  statement {
    sid     = "DescribeCluster"
    effect  = "Allow"
    actions = ["eks:DescribeCluster"]
    resources = [
      format(
        "arn:aws:eks:%s:%s:cluster/%s",
        var.aws_region,
        data.aws_caller_identity.current.account_id,
        data.aws_ssm_parameter.upstream["eks_cluster_name"].value,
      ),
    ]
  }

  statement {
    sid    = "ReadStageDeployParameters"
    effect = "Allow"
    actions = [
      "ssm:GetParameter",
    ]
    resources = [
      data.aws_ssm_parameter.upstream["eks_cluster_name"].arn,
      data.aws_ssm_parameter.migration_secret_arn[local.github_environment_api_stage[each.key]].arn,
      aws_ssm_parameter.service_order_bus_name[local.github_environment_api_stage[each.key]].arn,
      aws_ssm_parameter.service_order_publisher_role_arn[local.github_environment_api_stage[each.key]].arn,
    ]
  }
}

data "aws_iam_policy_document" "github_frontend_deploy" {
  for_each = var.enable_github_oidc ? toset(["staging", "production"]) : toset([])

  statement {
    sid       = "ListStageFrontendBucket"
    effect    = "Allow"
    actions   = ["s3:GetBucketLocation", "s3:ListBucket"]
    resources = [aws_s3_bucket.frontend[local.github_environment_api_stage[each.key]].arn]
  }

  statement {
    sid    = "DeployStageFrontendObjects"
    effect = "Allow"
    actions = [
      "s3:PutObject",
      "s3:DeleteObject",
    ]
    resources = [
      "${aws_s3_bucket.frontend[local.github_environment_api_stage[each.key]].arn}/*",
    ]
  }

  statement {
    sid       = "InvalidateStageFrontendDistribution"
    effect    = "Allow"
    actions   = ["cloudfront:CreateInvalidation"]
    resources = [aws_cloudfront_distribution.frontend[local.github_environment_api_stage[each.key]].arn]
  }

  statement {
    sid     = "ReadStageFrontendParameters"
    effect  = "Allow"
    actions = ["ssm:GetParameter"]
    resources = [

      aws_ssm_parameter.frontend_bucket_name[local.github_environment_api_stage[each.key]].arn,
      aws_ssm_parameter.frontend_distribution_id[local.github_environment_api_stage[each.key]].arn,
    ]
  }
}

resource "aws_iam_role_policy" "github_deploy_eks" {
  for_each = var.enable_github_oidc ? toset(["staging", "production"]) : toset([])

  name   = "${each.key}-deploy"
  role   = aws_iam_role.github_deploy[each.key].id
  policy = data.aws_iam_policy_document.github_deploy_eks[each.key].json
}

resource "aws_iam_role_policy" "github_frontend_deploy" {
  for_each = var.enable_github_oidc ? toset(["staging", "production"]) : toset([])

  name   = "${each.key}-frontend-deploy"
  role   = aws_iam_role.github_frontend_deploy[each.key].id
  policy = data.aws_iam_policy_document.github_frontend_deploy[each.key].json
}

data "aws_iam_policy_document" "github_auth_preflight_assume" {
  count = var.enable_github_oidc ? 1 : 0

  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github[0].arn]
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

data "aws_iam_policy_document" "github_auth_preflight" {
  count = var.enable_github_oidc ? 1 : 0

  statement {
    sid     = "ReadExactAuthAndNetworkContracts"
    effect  = "Allow"
    actions = ["ssm:GetParameters"]
    resources = [
      "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter/auto-shop/staging/auth/customer-token/function-arn/hml",
      "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter/auto-shop/staging/auth/customer-token/function-arn/prd",
      "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter/auto-shop/staging/network/vpc-id",
      "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter/auto-shop/staging/network/workload-private-subnet-ids",
      "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter/auto-shop/staging/network/lambda-security-group-id",
    ]
  }

  statement {
    sid     = "InspectExactPersistentAuthFunctions"
    effect  = "Allow"
    actions = ["lambda:GetFunctionConfiguration"]
    resources = [
      "arn:aws:lambda:${var.aws_region}:${data.aws_caller_identity.current.account_id}:function:${var.auth_lambda_function_name}-hml",
      "arn:aws:lambda:${var.aws_region}:${data.aws_caller_identity.current.account_id}:function:${var.auth_lambda_function_name}-prd",
    ]
  }
}

resource "aws_iam_role" "github_auth_preflight" {
  count = var.enable_github_oidc ? 1 : 0

  name                 = "auto-shop-staging-github-auth-preflight"
  description          = "Read-only preflight for persistent customer-auth Lambdas before staging session resources open."
  max_session_duration = 3600
  assume_role_policy   = data.aws_iam_policy_document.github_auth_preflight_assume[0].json
  tags                 = local.common_tags
}

resource "aws_iam_role_policy" "github_auth_preflight" {
  count = var.enable_github_oidc ? 1 : 0

  name   = "auth-preflight-read-only"
  role   = aws_iam_role.github_auth_preflight[0].id
  policy = data.aws_iam_policy_document.github_auth_preflight[0].json
}

output "github_deploy_role_arn_staging" {
  description = "IAM role ARN for GitHub Environment hml (variable AWS_DEPLOY_ROLE_ARN_HML)."
  value       = var.enable_github_oidc ? aws_iam_role.github_deploy["staging"].arn : null
}

output "github_deploy_role_arn_production" {
  description = "IAM role ARN for GitHub Environment prd (variable AWS_DEPLOY_ROLE_ARN_PRD)."
  value       = var.enable_github_oidc ? aws_iam_role.github_deploy["production"].arn : null
}

output "github_frontend_deploy_role_arn_staging" {
  description = "IAM role ARN for GitHub Environment hml frontend publication."
  value       = var.enable_github_oidc ? aws_iam_role.github_frontend_deploy["staging"].arn : null
}

output "github_frontend_deploy_role_arn_production" {
  description = "IAM role ARN for GitHub Environment prd frontend publication."
  value       = var.enable_github_oidc ? aws_iam_role.github_frontend_deploy["production"].arn : null
}

output "github_auth_preflight_role_arn" {
  description = "Read-only role ARN assumed by the operations environment before opening session resources."
  value       = var.enable_github_oidc ? aws_iam_role.github_auth_preflight[0].arn : null
}
