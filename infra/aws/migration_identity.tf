locals {
  migration_namespaces = {
    staging    = "auto-shop-hml"
    production = "auto-shop-prd"
  }

  cluster_arn = format(
    "arn:aws:eks:%s:%s:cluster/%s",
    var.aws_region,
    data.aws_caller_identity.current.account_id,
    data.aws_ssm_parameter.upstream["eks_cluster_name"].value,
  )
}

data "aws_iam_policy_document" "migration_pod_identity_assume" {
  for_each = local.migration_namespaces

  statement {
    actions = ["sts:AssumeRole", "sts:TagSession"]

    principals {
      type        = "Service"
      identifiers = ["pods.eks.amazonaws.com"]
    }

    condition {
      test     = "ArnEquals"
      variable = "aws:SourceArn"
      values   = [local.cluster_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }

    condition {
      test     = "StringEquals"
      variable = "aws:RequestTag/kubernetes-namespace"
      values   = [each.value]
    }

    condition {
      test     = "StringEquals"
      variable = "aws:RequestTag/kubernetes-service-account"
      values   = ["auto-shop-migration"]
    }
  }
}

resource "aws_iam_role" "migration_owner" {
  for_each = local.migration_namespaces

  name               = "${local.name_prefix}-${each.key}-migration-owner"
  assume_role_policy = data.aws_iam_policy_document.migration_pod_identity_assume[each.key].json
}

resource "aws_iam_role_policy_attachment" "migration_owner_secret_read" {
  for_each = local.migration_namespaces

  role       = aws_iam_role.migration_owner[each.key].name
  policy_arn = data.aws_ssm_parameter.migration_owner_secret_read_policy_arn.value
}

resource "aws_eks_pod_identity_association" "migration_owner" {
  for_each = local.migration_namespaces

  cluster_name    = data.aws_ssm_parameter.upstream["eks_cluster_name"].value
  namespace       = each.value
  service_account = "auto-shop-migration"
  role_arn        = aws_iam_role.migration_owner[each.key].arn

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-${each.key}-migration-owner"
  })
}
