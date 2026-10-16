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
  }
}

resource "aws_iam_role" "github_deploy" {
  for_each = var.enable_github_oidc ? toset(["staging", "production"]) : toset([])

  name               = "${local.name_prefix}-github-${each.key}"
  assume_role_policy = data.aws_iam_policy_document.github_deploy_assume[each.key].json
}

data "aws_iam_policy_document" "github_deploy_eks" {
  statement {
    sid    = "DescribeCluster"
    effect = "Allow"
    actions = [
      "eks:DescribeCluster",
      "eks:ListClusters",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "github_deploy_eks" {
  for_each = var.enable_github_oidc ? toset(["staging", "production"]) : toset([])

  name   = "${each.key}-eks-describe"
  role   = aws_iam_role.github_deploy[each.key].id
  policy = data.aws_iam_policy_document.github_deploy_eks.json
}

output "github_deploy_role_arn_staging" {
  description = "IAM role ARN for GitHub Environment staging (secret AWS_DEPLOY_ROLE_ARN)."
  value       = var.enable_github_oidc ? aws_iam_role.github_deploy["staging"].arn : null
}

output "github_deploy_role_arn_production" {
  description = "IAM role ARN for GitHub Environment production."
  value       = var.enable_github_oidc ? aws_iam_role.github_deploy["production"].arn : null
}
