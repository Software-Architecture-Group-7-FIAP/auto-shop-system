variable "aws_region" {
  description = "AWS region for API Gateway, Lambda and WAF."
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Prefix for AWS resource names."
  type        = string
  default     = "auto-shop"
}

variable "environment" {
  description = "Deployment stage: dev, staging or prod."
  type        = string

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be dev, staging or prod."
  }
}

variable "backend_base_url" {
  description = "Public or internal base URL of the Kubernetes backend (scheme + host, no trailing slash)."
  type        = string
}

variable "jwt_secret" {
  description = "HS256 secret shared with the FastAPI backend (ACCESS_TOKEN_SECRET or SECRET_KEY)."
  type        = string
  sensitive   = true
}

variable "domain_name" {
  description = "Optional custom domain for the API Gateway (e.g. api.autoshop.com)."
  type        = string
  default     = ""
}

variable "route53_zone_id" {
  description = "Optional Route53 hosted zone ID for domain validation and alias record."
  type        = string
  default     = ""
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

variable "waf_rate_limit" {
  description = "WAF rate-based rule limit per 5-minute window per IP."
  type        = number
  default     = 2000
}

variable "enable_waf_managed_rules" {
  description = "Attach AWS managed common rule set to the WAF Web ACL."
  type        = bool
  default     = true
}

variable "log_retention_days" {
  description = "CloudWatch retention for API Gateway access logs."
  type        = number
  default     = 30
}

variable "tags" {
  description = "Additional tags applied to all AWS resources."
  type        = map(string)
  default     = {}
}
