data "archive_file" "auth_login" {
  type        = "zip"
  source_dir  = "${path.module}/../../gateway/functions/auth_login"
  output_path = "${path.module}/build/auth_login.zip"
}

data "archive_file" "jwt_authorizer" {
  type        = "zip"
  source_dir  = "${path.module}/../../gateway/functions/jwt_authorizer"
  output_path = "${path.module}/build/jwt_authorizer.zip"
}

resource "aws_iam_role" "lambda_execution" {
  name = "${local.name_prefix}-gateway-lambda"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_lambda_function" "auth_login" {
  function_name = "${local.name_prefix}-auth-login"
  role          = aws_iam_role.lambda_execution.arn
  handler       = "handler.handler"
  runtime       = "python3.12"
  timeout       = 15
  memory_size   = 256

  filename         = data.archive_file.auth_login.output_path
  source_code_hash = data.archive_file.auth_login.output_base64sha256

  environment {
    variables = {
      BACKEND_BASE_URL         = local.backend_uri
      BACKEND_LOGIN_PATH       = "/api/v1/auth/gateway-login"
      REQUEST_TIMEOUT_SECONDS  = "10"
      MAX_RETRIES              = "2"
    }
  }
}

resource "aws_lambda_function" "jwt_authorizer" {
  function_name = "${local.name_prefix}-jwt-authorizer"
  role          = aws_iam_role.lambda_execution.arn
  handler       = "handler.handler"
  runtime       = "python3.12"
  timeout       = 5
  memory_size   = 128

  filename         = data.archive_file.jwt_authorizer.output_path
  source_code_hash = data.archive_file.jwt_authorizer.output_base64sha256

  environment {
    variables = {
      JWT_SECRET    = var.jwt_secret
      JWT_ALGORITHM = "HS256"
    }
  }
}

resource "aws_lambda_permission" "auth_login_apigw" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.auth_login.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.main.execution_arn}/*/*"
}

resource "aws_lambda_permission" "jwt_authorizer_apigw" {
  statement_id  = "AllowAuthorizerFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.jwt_authorizer.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.main.execution_arn}/authorizers/*"
}
