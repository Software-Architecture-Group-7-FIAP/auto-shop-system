locals {
  upstream_parameter_suffixes = {
    vpc_id             = "network/vpc-id"
    private_subnet_ids = "network/workload-private-subnet-ids"
    eks_cluster_name   = "eks/cluster-name"
    alb_arn            = "gateway/internal-alb-arn"
  }
}

data "aws_ssm_parameter" "upstream" {
  for_each = local.upstream_parameter_suffixes

  name = "${trimsuffix(var.upstream_ssm_prefix, "/")}/${each.value}"
}

data "aws_ssm_parameter" "alb_listener_arn" {
  for_each = local.api_stages

  name = "${trimsuffix(var.upstream_ssm_prefix, "/")}/gateway/listener-arn/${each.key}"
}

data "aws_lb" "internal" {
  arn = data.aws_ssm_parameter.upstream["alb_arn"].value
}

data "aws_lb_listener" "internal" {
  for_each = local.api_stages

  arn = data.aws_ssm_parameter.alb_listener_arn[each.key].value
}

data "aws_ssm_parameter" "customer_auth_lambda_arn" {
  for_each = local.api_stages

  name = "${trimsuffix(var.upstream_ssm_prefix, "/")}/auth/customer-token/function-arn/${each.key}"
}

data "aws_ssm_parameter" "migration_secret_arn" {
  for_each = toset(values(local.migration_database_stages))

  name = "${trimsuffix(var.upstream_ssm_prefix, "/")}/database/secrets/migrations-${each.key}-arn"
}

data "aws_ssm_parameter" "migration_secret_read_policy_arn" {
  for_each = toset(values(local.migration_database_stages))

  name = "${trimsuffix(var.upstream_ssm_prefix, "/")}/database/iam/migrations-${each.key}-read-policy-arn"
}

locals {
  alb_listener_security_group_rules = {
    for rule in flatten([
      for stage, listener in data.aws_lb_listener.internal : [
        for security_group_id in data.aws_lb.internal.security_groups : {
          key               = "${stage}-${security_group_id}"
          listener_port     = listener.port
          security_group_id = security_group_id
        }
      ]
    ]) : rule.key => rule if var.enable_alb_security_group_rules
  }
}

resource "aws_security_group" "api_gateway_vpc_link" {
  name        = "${local.name_prefix}-gateway-vpc-link"
  description = "Egress from API Gateway VPC Link to the internal Auto Shop ALB listener."
  vpc_id      = data.aws_ssm_parameter.upstream["vpc_id"].value
  egress      = []

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-gateway-vpc-link"
  })
}

resource "aws_vpc_security_group_egress_rule" "vpc_link_to_alb" {
  for_each = local.alb_listener_security_group_rules

  security_group_id            = aws_security_group.api_gateway_vpc_link.id
  description                  = "Allow API Gateway VPC Link to the internal ALB listener."
  ip_protocol                  = "tcp"
  from_port                    = each.value.listener_port
  to_port                      = each.value.listener_port
  referenced_security_group_id = each.value.security_group_id
}

resource "aws_vpc_security_group_ingress_rule" "alb_from_vpc_link" {
  for_each = local.alb_listener_security_group_rules

  security_group_id            = each.value.security_group_id
  description                  = "Allow API Gateway VPC Link on the internal ALB listener port."
  ip_protocol                  = "tcp"
  from_port                    = each.value.listener_port
  to_port                      = each.value.listener_port
  referenced_security_group_id = aws_security_group.api_gateway_vpc_link.id
}

resource "aws_apigatewayv2_vpc_link" "gateway" {
  name               = "${local.name_prefix}-gateway-vpc-link"
  security_group_ids = [aws_security_group.api_gateway_vpc_link.id]
  subnet_ids = [
    for subnet_id in split(",", data.aws_ssm_parameter.upstream["private_subnet_ids"].value) :
    trimspace(subnet_id) if trimspace(subnet_id) != ""
  ]

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-gateway-vpc-link"
  })
}
