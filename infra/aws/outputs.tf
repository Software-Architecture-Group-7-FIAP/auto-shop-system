output "api_gateway_id" {
  description = "REST API Gateway identifier."
  value       = aws_api_gateway_rest_api.main.id
}

output "api_gateway_invoke_url" {
  description = "Default invoke URLs by API stage."
  value       = { for stage, api_stage in aws_api_gateway_stage.main : stage => api_stage.invoke_url }
}

output "api_gateway_stage_arn" {
  description = "Stage ARNs used for WAF association and monitoring."
  value       = { for stage, api_stage in aws_api_gateway_stage.main : stage => api_stage.arn }
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
  value       = var.enable_custom_domains ? aws_api_gateway_domain_name.main[0].domain_name : null
}

output "custom_domain_target" {
  description = "Regional domain name target for DNS alias records."
  value       = var.enable_custom_domains ? aws_api_gateway_domain_name.main[0].regional_domain_name : null
}
