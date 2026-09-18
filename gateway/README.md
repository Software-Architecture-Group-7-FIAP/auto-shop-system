# Gateway — Lambdas Auto Shop

Funções Lambda usadas pelo API Gateway (issue #88). Código em `gateway/functions/`.

## `auth_login`

Proxy de autenticação pública:

- Entrada: `POST /auth/login` `{ "username", "password" }`
- Saída: resposta JSON do backend (`access_token`, `token_type`, `expires_in`, ...)
- Retry configurável para erros 5xx do backend

Variáveis:

- `BACKEND_BASE_URL`
- `BACKEND_LOGIN_PATH` (default `/api/v1/auth/gateway-login`)
- `REQUEST_TIMEOUT_SECONDS`
- `MAX_RETRIES`

## `jwt_authorizer`

Authorizer TOKEN para rotas protegidas:

- Valida JWT HS256 com o mesmo segredo do backend
- Propaga `username` e `sessionId` no contexto do API Gateway
- Headers repassados ao backend: `X-Gateway-User`, `X-Gateway-Session`, `X-Correlation-ID`

Variáveis:

- `JWT_SECRET`
- `JWT_ALGORITHM` (default `HS256`)
