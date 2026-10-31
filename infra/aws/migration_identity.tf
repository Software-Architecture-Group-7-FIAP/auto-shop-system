locals {
  migration_database_stages = {
    staging    = "hml"
    production = "prd"
  }
  migration_namespaces = {
    for stage, database_stage in local.migration_database_stages :
    stage => "auto-shop-${database_stage}"
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

resource "aws_iam_role" "migration" {
  for_each = local.migration_namespaces

  name               = "${local.name_prefix}-${each.key}-migration"
  assume_role_policy = data.aws_iam_policy_document.migration_pod_identity_assume[each.key].json
}

resource "aws_iam_role_policy_attachment" "migration_secret_read" {
  for_each = local.migration_namespaces

  role       = aws_iam_role.migration[each.key].name
  policy_arn = data.aws_ssm_parameter.migration_secret_read_policy_arn[local.migration_database_stages[each.key]].value
}

resource "aws_eks_pod_identity_association" "migration" {
  for_each = local.migration_namespaces

  cluster_name    = data.aws_ssm_parameter.upstream["eks_cluster_name"].value
  namespace       = each.value
  service_account = "auto-shop-migration"
  role_arn        = aws_iam_role.migration[each.key].arn

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-${each.key}-migration"
  })

  depends_on = [aws_iam_role_policy_attachment.migration_secret_read]
}

moved {
  from = aws_iam_role.migration_owner["staging"]
  to   = aws_iam_role.migration["staging"]
}

moved {
  from = aws_iam_role.migration_owner["production"]
  to   = aws_iam_role.migration["production"]
}

moved {
  from = aws_iam_role_policy_attachment.migration_owner_secret_read["staging"]
  to   = aws_iam_role_policy_attachment.migration_secret_read["staging"]
}

moved {
  from = aws_iam_role_policy_attachment.migration_owner_secret_read["production"]
  to   = aws_iam_role_policy_attachment.migration_secret_read["production"]
}

moved {
  from = aws_eks_pod_identity_association.migration_owner["staging"]
  to   = aws_eks_pod_identity_association.migration["staging"]
}

moved {
  from = aws_eks_pod_identity_association.migration_owner["production"]
  to   = aws_eks_pod_identity_association.migration["production"]
}
