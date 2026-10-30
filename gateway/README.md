# API Gateway Lambda functions

The API Gateway routes web-session login, refresh, logout, and admin requests to the FastAPI backend. Customer token and JWKS routes invoke the customer-auth Lambda published for each stage.

## Login routes

API Gateway forwards `POST /auth/login` directly to FastAPI at
`/api/v1/auth/gateway-login`. The backend path is not published as a separate
API Gateway resource. There is no login proxy Lambda; the public alias issues a
Bearer token for the Postman staging flow and does not set browser session
cookies.

## jwt_authorizer

The REQUEST authorizer checks HS256 JWTs from either the `Authorization: Bearer` header or the `oficina_access` HttpOnly cookie. It requires audience `gateway` for bearer tokens and `web` for cookie sessions. API Gateway policy caching is disabled, and the backend revalidates the forwarded bearer token or cookie.

Environment:

- JWT_SECRET_ARN: ARN of the Secrets Manager secret containing the same signing value as backend ACCESS_TOKEN_SECRET.
- JWT_ALGORITHM: HS256.

The authorizer execution role can read only the configured secret ARN. The secret value is fetched at runtime and cached for five minutes. Terraform state contains the ARN, never the secret value.
