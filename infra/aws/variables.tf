variable "aws_region" {
  description = "AWS region for the API, ACM certificate, WAF and CloudFront."
  type        = string
  default     = "us-east-1"

  validation {
    condition     = var.aws_region == "us-east-1"
    error_message = "The API and CloudFront ACM certificate must be managed in us-east-1."
  }
}

variable "project_name" {
  description = "Prefix for AWS resource names."
  type        = string
  default     = "auto-shop"
}

variable "environment" {
  description = "Shared infrastructure session name used in resource names and tags."
  type        = string

  validation {
    condition     = var.environment == "staging"
    error_message = "This Terraform root manages the shared staging AWS session only."
  }
}

variable "upstream_ssm_prefix" {
  description = "Fixed SSM prefix exported by the upstream staging stacks and read by the auth preflight role."
  type        = string
  default     = "/auto-shop/staging"

  validation {
    condition     = var.upstream_ssm_prefix == "/auto-shop/staging"
    error_message = "upstream_ssm_prefix must match the shared /auto-shop/staging contract used by the auth preflight."
  }
}

variable "api_domain_name" {
  description = "Public API custom domain managed outside Route 53 (Registro.br)."
  type        = string
  default     = "api.oficina-workshop.com.br"
}

variable "jwt_secret_arn" {
  description = "Secrets Manager ARN containing the plaintext HS256 signing secret used by the backend."
  type        = string

  validation {
    condition     = can(regex("^arn:aws:secretsmanager:[a-z0-9-]+:[0-9]{12}:secret:.+$", var.jwt_secret_arn))
    error_message = "jwt_secret_arn must be the ARN of one Secrets Manager secret."
  }
}

variable "frontend_domains" {
  description = "CloudFront alternate domain names for the static frontend per stage."
  type        = map(string)
  default = {
    hml = "app-hml.oficina-workshop.com.br"
    prd = "app.oficina-workshop.com.br"
  }

  validation {
    condition     = toset(keys(var.frontend_domains)) == toset(["hml", "prd"])
    error_message = "frontend_domains must define hml and prd."
  }
}

variable "enable_custom_domains" {
  description = "Enable API and CloudFront aliases after ACM DNS validation CNAMEs are published at Registro.br."
  type        = bool
  default     = false
}

variable "disable_execute_api_endpoint" {
  description = "Disable the execute-api host only after both custom-domain stages pass their smoke checks."
  type        = bool
  default     = false
}

variable "throttle_burst_limit" {
  description = "API Gateway stage burst limit."
  type        = number
  default     = 100
}

variable "throttle_rate_limit" {
  description = "API Gateway stage steady-state rate limit (requests per second)."
  type        = number
  default     = 50
}

variable "waf_regional_rate_limit" {
  description = "Coarse Regional WAF cap per source IP; CloudFront WAF applies the viewer-specific limits."
  type        = number
  default     = 20000
}

variable "waf_rate_limit" {
  description = "CloudFront WAF rate-based rule limit per 5-minute window per viewer IP for customer-token requests."
  type        = number
  default     = 100
}

variable "waf_auth_rate_limit" {
  description = "CloudFront WAF rate-based rule limit per 5-minute window per viewer IP for authentication requests."
  type        = number
  default     = 300
}

variable "waf_public_rate_limit" {
  description = "CloudFront WAF rate-based rule limit per 5-minute window per viewer IP for public and customer API requests."
  type        = number
  default     = 1000
}

variable "enable_alb_security_group_rules" {
  description = "Manage the API Gateway VPC Link and internal ALB listener security-group references. Disable only during the coordinated overnight maintenance window."
  type        = bool
  default     = true
}

variable "enable_waf_managed_rules" {
  description = "Attach AWS managed common rule set to the WAF Web ACL."
  type        = bool
  default     = true
}

variable "log_retention_days" {
  description = "CloudWatch retention for API Gateway and WAF logs."
  type        = number
  default     = 30
}

variable "tags" {
  description = "Additional tags applied to all AWS resources."
  type        = map(string)
  default     = {}
}
