output "api_gateway_id" {
  description = "REST API Gateway identifier."
  value       = aws_api_gateway_rest_api.main.id
}

output "api_gateway_invoke_url" {
  description = "Default invoke URL for the configured stage."
  value       = aws_api_gateway_stage.main.invoke_url
}

output "api_gateway_stage_arn" {
  description = "Stage ARN used for WAF association and monitoring."
  value       = aws_api_gateway_stage.main.arn
}

output "auth_login_lambda_arn" {
  description = "Lambda ARN for public authentication."
  value       = aws_lambda_function.auth_login.arn
}

output "jwt_authorizer_lambda_arn" {
  description = "Lambda ARN for JWT TOKEN authorizer."
  value       = aws_lambda_function.jwt_authorizer.arn
}

output "waf_web_acl_arn" {
  description = "Regional WAF Web ACL ARN."
  value       = aws_wafv2_web_acl.main.arn
}

output "access_log_group_name" {
  description = "CloudWatch log group for API Gateway access logs."
  value       = aws_cloudwatch_log_group.api_gateway_access.name
}

output "custom_domain_name" {
  description = "Configured custom domain, when enabled."
  value       = var.domain_name != "" ? aws_api_gateway_domain_name.main[0].domain_name : null
}

output "custom_domain_target" {
  description = "Regional domain name target for DNS alias records."
  value       = var.domain_name != "" ? aws_api_gateway_domain_name.main[0].regional_domain_name : null
}
