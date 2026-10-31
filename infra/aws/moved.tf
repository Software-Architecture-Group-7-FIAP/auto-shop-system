moved {
  from = aws_api_gateway_integration.auth_login_lambda
  to   = aws_api_gateway_integration.auth_login_backend
}

moved {
  from = aws_iam_role.migration_owner["staging"]
  to   = aws_iam_role.migration["staging"]
}

moved {
  from = aws_iam_role_policy_attachment.migration_owner_secret_read["staging"]
  to   = aws_iam_role_policy_attachment.migration_secret_read["staging"]
}

moved {
  from = aws_eks_pod_identity_association.migration_owner["staging"]
  to   = aws_eks_pod_identity_association.migration["staging"]
}

moved {
  from = aws_iam_role.migration_owner["production"]
  to   = aws_iam_role.migration["production"]
}

moved {
  from = aws_iam_role_policy_attachment.migration_owner_secret_read["production"]
  to   = aws_iam_role_policy_attachment.migration_secret_read["production"]
}

moved {
  from = aws_eks_pod_identity_association.migration_owner["production"]
  to   = aws_eks_pod_identity_association.migration["production"]
}
