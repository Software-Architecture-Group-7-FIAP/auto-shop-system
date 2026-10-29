resource "aws_api_gateway_rest_api" "main" {
  name                         = "${local.name_prefix}-gateway"
  description                  = "Auto Shop public API Gateway"
  disable_execute_api_endpoint = var.disable_execute_api_endpoint

  endpoint_configuration {
    types = ["REGIONAL"]
  }
}

resource "aws_api_gateway_authorizer" "jwt" {
  name                             = "${local.name_prefix}-jwt-authorizer"
  rest_api_id                      = aws_api_gateway_rest_api.main.id
  authorizer_uri                   = aws_lambda_function.jwt_authorizer.invoke_arn
  type                             = "TOKEN"
  identity_source                  = "method.request.header.Authorization"
  authorizer_result_ttl_in_seconds = 300
}

resource "aws_api_gateway_resource" "auth" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_rest_api.main.root_resource_id
  path_part   = "auth"
}

resource "aws_api_gateway_resource" "auth_login" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_resource.auth.id
  path_part   = "login"
}

resource "aws_api_gateway_resource" "auth_customer" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_resource.auth.id
  path_part   = "customer"
}

resource "aws_api_gateway_resource" "auth_customer_token" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_resource.auth_customer.id
  path_part   = "token"
}

resource "aws_api_gateway_resource" "well_known" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_rest_api.main.root_resource_id
  path_part   = ".well-known"
}

resource "aws_api_gateway_resource" "jwks" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_resource.well_known.id
  path_part   = "jwks.json"
}

resource "aws_api_gateway_resource" "api" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_rest_api.main.root_resource_id
  path_part   = "api"
}

resource "aws_api_gateway_resource" "api_v1" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_resource.api.id
  path_part   = "v1"
}

resource "aws_api_gateway_resource" "api_v1_auth" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_resource.api_v1.id
  path_part   = "auth"
}

resource "aws_api_gateway_resource" "api_v1_auth_proxy" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_resource.api_v1_auth.id
  path_part   = "{proxy+}"
}

resource "aws_api_gateway_resource" "admin" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_resource.api_v1.id
  path_part   = "admin"
}

resource "aws_api_gateway_resource" "admin_proxy" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_resource.admin.id
  path_part   = "{proxy+}"
}

resource "aws_api_gateway_resource" "public" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_resource.api_v1.id
  path_part   = "public"
}

resource "aws_api_gateway_resource" "customer" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_resource.api_v1.id
  path_part   = "customer"
}

resource "aws_api_gateway_resource" "customer_proxy" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_resource.customer.id
  path_part   = "{proxy+}"
}

resource "aws_api_gateway_resource" "public_proxy" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_resource.public.id
  path_part   = "{proxy+}"
}

resource "aws_api_gateway_resource" "health" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_rest_api.main.root_resource_id
  path_part   = "health"
}

resource "aws_api_gateway_resource" "health_proxy" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_resource.health.id
  path_part   = "{proxy+}"
}

resource "aws_api_gateway_method" "api_v1_auth_any" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.api_v1_auth_proxy.id
  http_method   = "ANY"
  authorization = "NONE"

  request_parameters = {
    "method.request.path.proxy" = true
  }
}

resource "aws_api_gateway_integration" "api_v1_auth_http" {
  rest_api_id             = aws_api_gateway_rest_api.main.id
  resource_id             = aws_api_gateway_resource.api_v1_auth_proxy.id
  http_method             = aws_api_gateway_method.api_v1_auth_any.http_method
  integration_http_method = "ANY"
  type                    = "HTTP_PROXY"
  connection_type         = "VPC_LINK"
  connection_id           = aws_apigatewayv2_vpc_link.gateway.id
  integration_target      = data.aws_lb.internal.arn
  uri                     = "http://${var.api_domain_name}:$${stageVariables.backendListenerPort}/api/v1/auth/{proxy}"

  request_parameters = {
    "integration.request.path.proxy"              = "method.request.path.proxy"
    "integration.request.header.X-Correlation-ID" = "context.requestId"
  }
}

resource "aws_api_gateway_method" "auth_login_post" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.auth_login.id
  http_method   = "POST"
  authorization = "NONE"
}

resource "aws_api_gateway_method" "auth_login_options" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.auth_login.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "auth_login_lambda" {
  rest_api_id             = aws_api_gateway_rest_api.main.id
  resource_id             = aws_api_gateway_resource.auth_login.id
  http_method             = aws_api_gateway_method.auth_login_post.http_method
  integration_http_method = "POST"
  type                    = "HTTP_PROXY"
  connection_type         = "VPC_LINK"
  connection_id           = aws_apigatewayv2_vpc_link.gateway.id
  integration_target      = data.aws_lb.internal.arn
  uri                     = "http://${var.api_domain_name}:$${stageVariables.backendListenerPort}/api/v1/auth/gateway-login"
}

resource "aws_api_gateway_integration" "auth_login_options_http" {
  rest_api_id             = aws_api_gateway_rest_api.main.id
  resource_id             = aws_api_gateway_resource.auth_login.id
  http_method             = aws_api_gateway_method.auth_login_options.http_method
  integration_http_method = "OPTIONS"
  type                    = "HTTP_PROXY"
  connection_type         = "VPC_LINK"
  connection_id           = aws_apigatewayv2_vpc_link.gateway.id
  integration_target      = data.aws_lb.internal.arn
  uri                     = "http://${var.api_domain_name}:$${stageVariables.backendListenerPort}/api/v1/auth/gateway-login"
}

resource "aws_api_gateway_method" "auth_customer_token_post" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.auth_customer_token.id
  http_method   = "POST"
  authorization = "NONE"
}

resource "aws_api_gateway_method" "auth_customer_token_options" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.auth_customer_token.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "auth_customer_token_options_lambda" {
  rest_api_id             = aws_api_gateway_rest_api.main.id
  resource_id             = aws_api_gateway_resource.auth_customer_token.id
  http_method             = aws_api_gateway_method.auth_customer_token_options.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = "arn:aws:apigateway:${var.aws_region}:lambda:path/2015-03-31/functions/$${stageVariables.customerAuthLambdaArn}/invocations"
}

resource "aws_api_gateway_integration" "auth_customer_token_lambda" {
  rest_api_id             = aws_api_gateway_rest_api.main.id
  resource_id             = aws_api_gateway_resource.auth_customer_token.id
  http_method             = aws_api_gateway_method.auth_customer_token_post.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = "arn:aws:apigateway:${var.aws_region}:lambda:path/2015-03-31/functions/$${stageVariables.customerAuthLambdaArn}/invocations"
}

resource "aws_api_gateway_method" "jwks_get" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.jwks.id
  http_method   = "GET"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "jwks_lambda" {
  rest_api_id             = aws_api_gateway_rest_api.main.id
  resource_id             = aws_api_gateway_resource.jwks.id
  http_method             = aws_api_gateway_method.jwks_get.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = "arn:aws:apigateway:${var.aws_region}:lambda:path/2015-03-31/functions/$${stageVariables.customerAuthLambdaArn}/invocations"
}

resource "aws_api_gateway_method" "admin_any" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.admin_proxy.id
  http_method   = "ANY"
  authorization = "CUSTOM"
  authorizer_id = aws_api_gateway_authorizer.jwt.id

  request_parameters = {
    "method.request.path.proxy" = true
  }
}

resource "aws_api_gateway_integration" "admin_http" {
  rest_api_id        = aws_api_gateway_rest_api.main.id
  resource_id        = aws_api_gateway_resource.admin_proxy.id
  http_method        = aws_api_gateway_method.admin_any.http_method
  type               = "HTTP_PROXY"
  uri                = "http://${var.api_domain_name}:$${stageVariables.backendListenerPort}/api/v1/admin/{proxy}"
  connection_type    = "VPC_LINK"
  connection_id      = aws_apigatewayv2_vpc_link.gateway.id
  integration_target = data.aws_lb.internal.arn

  integration_http_method = "ANY"

  request_parameters = {
    "integration.request.path.proxy"               = "method.request.path.proxy"
    "integration.request.header.X-Correlation-ID"  = "context.requestId"
    "integration.request.header.X-Gateway-User"    = "context.authorizer.username"
    "integration.request.header.X-Gateway-Session" = "context.authorizer.sessionId"
  }
}

resource "aws_api_gateway_method" "admin_options" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.admin_proxy.id
  http_method   = "OPTIONS"
  authorization = "NONE"

  request_parameters = {
    "method.request.path.proxy" = true
  }
}

resource "aws_api_gateway_integration" "admin_options_http" {
  rest_api_id             = aws_api_gateway_rest_api.main.id
  resource_id             = aws_api_gateway_resource.admin_proxy.id
  http_method             = aws_api_gateway_method.admin_options.http_method
  integration_http_method = "OPTIONS"
  type                    = "HTTP_PROXY"
  connection_type         = "VPC_LINK"
  connection_id           = aws_apigatewayv2_vpc_link.gateway.id
  integration_target      = data.aws_lb.internal.arn
  uri                     = "http://${var.api_domain_name}:$${stageVariables.backendListenerPort}/api/v1/admin/{proxy}"

  request_parameters = {
    "integration.request.path.proxy" = "method.request.path.proxy"
  }
}

resource "aws_api_gateway_method" "public_any" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.public_proxy.id
  http_method   = "ANY"
  authorization = "NONE"

  request_parameters = {
    "method.request.path.proxy" = true
  }
}

resource "aws_api_gateway_integration" "public_http" {
  rest_api_id        = aws_api_gateway_rest_api.main.id
  resource_id        = aws_api_gateway_resource.public_proxy.id
  http_method        = aws_api_gateway_method.public_any.http_method
  type               = "HTTP_PROXY"
  uri                = "http://${var.api_domain_name}:$${stageVariables.backendListenerPort}/api/v1/public/{proxy}"
  connection_type    = "VPC_LINK"
  connection_id      = aws_apigatewayv2_vpc_link.gateway.id
  integration_target = data.aws_lb.internal.arn

  integration_http_method = "ANY"

  request_parameters = {
    "integration.request.path.proxy"              = "method.request.path.proxy"
    "integration.request.header.X-Correlation-ID" = "context.requestId"
  }
}

resource "aws_api_gateway_method" "customer_any" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.customer_proxy.id
  http_method   = "ANY"
  authorization = "NONE"

  request_parameters = {
    "method.request.path.proxy" = true
  }
}

resource "aws_api_gateway_integration" "customer_http" {
  rest_api_id             = aws_api_gateway_rest_api.main.id
  resource_id             = aws_api_gateway_resource.customer_proxy.id
  http_method             = aws_api_gateway_method.customer_any.http_method
  type                    = "HTTP_PROXY"
  uri                     = "http://${var.api_domain_name}:$${stageVariables.backendListenerPort}/api/v1/customer/{proxy}"
  connection_type         = "VPC_LINK"
  connection_id           = aws_apigatewayv2_vpc_link.gateway.id
  integration_target      = data.aws_lb.internal.arn
  integration_http_method = "ANY"

  request_parameters = {
    "integration.request.path.proxy"              = "method.request.path.proxy"
    "integration.request.header.X-Correlation-ID" = "context.requestId"
  }
}

resource "aws_api_gateway_method" "health_any" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.health_proxy.id
  http_method   = "ANY"
  authorization = "NONE"

  request_parameters = {
    "method.request.path.proxy" = true
  }
}

resource "aws_api_gateway_integration" "health_http" {
  rest_api_id        = aws_api_gateway_rest_api.main.id
  resource_id        = aws_api_gateway_resource.health_proxy.id
  http_method        = aws_api_gateway_method.health_any.http_method
  type               = "HTTP_PROXY"
  uri                = "http://${var.api_domain_name}:$${stageVariables.backendListenerPort}/health/{proxy}"
  connection_type    = "VPC_LINK"
  connection_id      = aws_apigatewayv2_vpc_link.gateway.id
  integration_target = data.aws_lb.internal.arn

  integration_http_method = "ANY"

  request_parameters = {
    "integration.request.path.proxy"              = "method.request.path.proxy"
    "integration.request.header.X-Correlation-ID" = "context.requestId"
  }
}

resource "aws_api_gateway_deployment" "main" {
  rest_api_id = aws_api_gateway_rest_api.main.id

  triggers = {
    redeployment = sha1(jsonencode([
      aws_api_gateway_resource.api_v1_auth.id,
      aws_api_gateway_integration.api_v1_auth_http.id,
      aws_api_gateway_resource.auth_login.id,
      aws_api_gateway_integration.auth_login_lambda.id,
      aws_api_gateway_integration.auth_login_options_http.id,
      aws_api_gateway_integration.auth_customer_token_options_lambda.id,
      aws_api_gateway_integration.auth_customer_token_lambda.id,
      aws_api_gateway_integration.jwks_lambda.id,
      aws_api_gateway_integration.admin_http.id,
      aws_api_gateway_integration.admin_options_http.id,
      aws_api_gateway_integration.customer_http.id,
      aws_api_gateway_integration.public_http.id,
      aws_api_gateway_integration.health_http.id,
      aws_api_gateway_authorizer.jwt.id,
      aws_api_gateway_integration.auth_login_lambda.uri,
      aws_api_gateway_integration.auth_login_lambda.integration_target,
      aws_api_gateway_integration.api_v1_auth_http.uri,
      aws_api_gateway_integration.api_v1_auth_http.integration_target,
      aws_api_gateway_integration.auth_login_options_http.uri,
      aws_api_gateway_integration.auth_login_options_http.integration_target,
      aws_api_gateway_integration.auth_customer_token_options_lambda.uri,
      aws_api_gateway_integration.auth_customer_token_lambda.uri,
      aws_api_gateway_integration.jwks_lambda.uri,
      aws_api_gateway_integration.admin_http.uri,
      aws_api_gateway_integration.admin_http.integration_target,
      aws_api_gateway_integration.admin_options_http.uri,
      aws_api_gateway_integration.admin_options_http.integration_target,
      aws_api_gateway_integration.customer_http.uri,
      aws_api_gateway_integration.customer_http.integration_target,
      aws_api_gateway_integration.public_http.uri,
      aws_api_gateway_integration.public_http.integration_target,
      aws_api_gateway_integration.health_http.uri,
      aws_api_gateway_integration.health_http.integration_target,
    ]))
  }

  lifecycle {
    create_before_destroy = true
  }

  depends_on = [
    aws_api_gateway_integration.api_v1_auth_http,
    aws_api_gateway_integration.auth_login_lambda,
    aws_api_gateway_integration.auth_login_options_http,
    aws_api_gateway_integration.auth_customer_token_options_lambda,
    aws_api_gateway_integration.auth_customer_token_lambda,
    aws_api_gateway_integration.jwks_lambda,
    aws_api_gateway_integration.admin_http,
    aws_api_gateway_integration.admin_options_http,
    aws_api_gateway_integration.customer_http,
    aws_api_gateway_integration.public_http,
    aws_api_gateway_integration.health_http,
  ]
}

resource "aws_api_gateway_stage" "main" {
  for_each = local.api_stages

  deployment_id = aws_api_gateway_deployment.main.id
  rest_api_id   = aws_api_gateway_rest_api.main.id
  stage_name    = each.key
  variables = {
    backendListenerPort   = tostring(data.aws_lb_listener.internal[each.key].port)
    customerAuthLambdaArn = data.aws_ssm_parameter.customer_auth_lambda_arn[each.key].value
  }

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_gateway_access.arn
    format = jsonencode({
      requestId      = "$context.requestId"
      ip             = "$context.identity.sourceIp"
      requestTime    = "$context.requestTime"
      httpMethod     = "$context.httpMethod"
      resourcePath   = "$context.resourcePath"
      status         = "$context.status"
      protocol       = "$context.protocol"
      responseLength = "$context.responseLength"
      latencyMs      = "$context.responseLatency"
    })
  }

  depends_on = [aws_api_gateway_account.main]
}

resource "aws_api_gateway_method_settings" "main" {
  for_each = local.api_stages

  rest_api_id = aws_api_gateway_rest_api.main.id
  stage_name  = aws_api_gateway_stage.main[each.key].stage_name
  method_path = "*/*"

  settings {
    metrics_enabled        = true
    logging_level          = "INFO"
    data_trace_enabled     = false
    throttling_burst_limit = var.throttle_burst_limit
    throttling_rate_limit  = var.throttle_rate_limit
  }
}

resource "aws_api_gateway_usage_plan" "main" {
  name = "${local.name_prefix}-usage-plan"

  dynamic "api_stages" {
    for_each = local.api_stages

    content {
      api_id = aws_api_gateway_rest_api.main.id
      stage  = aws_api_gateway_stage.main[api_stages.value].stage_name
    }
  }

  throttle_settings {
    burst_limit = var.throttle_burst_limit
    rate_limit  = var.throttle_rate_limit
  }
}
