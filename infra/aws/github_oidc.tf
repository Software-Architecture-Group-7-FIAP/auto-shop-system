# GitHub Actions OIDC → IAM roles for EKS deploy (issue #90).
# Apply once per AWS account; map role ARNs to GitHub Environment secrets.

variable "enable_github_oidc" {
  description = "Create GitHub OIDC provider and deploy roles."
  type        = bool
  default     = false
}

variable "github_repository" {
  description = "GitHub repo in org/name form allowed to assume deploy roles."
  type        = string
  default     = "Software-Architecture-Group-7-FIAP/auto-shop-system"
}

variable "github_oidc_thumbprint" {
  description = "GitHub Actions OIDC root CA thumbprint (default valid for github.com)."
  type        = string
  default     = "6938fd4d98bab03faadb97b34396831e3780aea1"
}

locals {
  github_environment_api_stage = {
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
      values   = ["repo:${var.github_repository}:environment:${each.key}"]
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

output "github_deploy_role_arn_staging" {
  description = "IAM role ARN for GitHub Environment staging (secret AWS_DEPLOY_ROLE_ARN)."
  value       = var.enable_github_oidc ? aws_iam_role.github_deploy["staging"].arn : null
}

output "github_deploy_role_arn_production" {
  description = "IAM role ARN for GitHub Environment production."
  value       = var.enable_github_oidc ? aws_iam_role.github_deploy["production"].arn : null
}
