provider "aws" {
  region = var.aws_region

  default_tags {
    tags = merge(
      {
        Project     = var.project_name
        Environment = var.environment
        ManagedBy   = "terraform"
        Component   = "api-gateway"
      },
      var.tags,
    )
  }
}

data "aws_caller_identity" "current" {}

data "aws_region" "current" {}

data "aws_partition" "current" {}

locals {
  name_prefix = "${var.project_name}-${var.environment}"
  api_stages  = toset(["hml", "prd"])

  common_tags = {
    Project     = var.project_name
    Environment = var.environment
    Component   = "api-gateway"
  }

  service_order_alert_topic_arn = "arn:${data.aws_partition.current.partition}:sns:${data.aws_region.current.region}:${data.aws_caller_identity.current.account_id}:${local.name_prefix}-service-order-alerts"

}
