# API Gateway Lambda functions

The API Gateway routes web-session login, refresh, logout, and admin requests to the FastAPI backend. Customer token and JWKS routes invoke the customer-auth Lambda published for each stage.

## auth_login (legacy)

The legacy proxy Lambda remains in the Terraform source, but the API Gateway login route targets FastAPI directly so it can set the web-session cookies expected by Angular. Do not use this Lambda for browser session login.

## jwt_authorizer

The TOKEN authorizer checks HS256 JWTs and adds username and sessionId to the API Gateway context.

Environment:

- JWT_SECRET_ARN: ARN of the Secrets Manager secret containing the same signing value as backend ACCESS_TOKEN_SECRET.
- JWT_ALGORITHM: HS256.

The authorizer execution role can read only the configured secret ARN. The secret value is fetched at runtime and cached for five minutes. Terraform state contains the ARN, never the secret value.
