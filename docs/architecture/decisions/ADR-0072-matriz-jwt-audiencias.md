# ADR-0072: Matriz de JWT — audiências web, gateway e cliente

- **Status:** Aceito
- **Data:** 2026-10-23
- **Issues:** [#95](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/issues/95), [#64–#65](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/issues/64) (cliente)
- **Relacionado:** [ADR-0064](./ADR-0064-autenticacao-cliente-cpf-jwt.md)

## Contexto

Três fluxos de autenticação coexistem no ecossistema: sessão admin no painel web, login via API Gateway para integrações serverless e JWT de cliente emitido por Lambda (RS256/JWKS). Misturar validadores ou audiências quebraria isolamento entre admin e cliente.

## Decisão

| Fluxo | Emissor | Algoritmo | `aud` | Transporte típico | Validador |
| --- | --- | --- | --- | --- | --- |
| **Web admin** | FastAPI (`AuthService`) | HS256 (segredo app) | `web` | Cookies HttpOnly + CSRF | `get_current_user` — exige `aud=web` |
| **Gateway admin** | FastAPI após Lambda login | HS256 (mesmo segredo) | `gateway` | Header `Authorization: Bearer` | Authorizer Lambda no API Gateway + backend em `/gateway-login` |
| **Cliente** | Lambda identidade | RS256 + KMS | `auto-shop-api` | Bearer nas rotas `/api/v1/customer/*` | `CustomerJwtVerifier` (JWKS HTTPS) |

Constantes de código admin: `JWT_AUD_WEB` e `JWT_AUD_GATEWAY` em `src/domain/auth/jwt_audience.py`.

Claims mínimos do cliente: `sub`, `principal_type=customer`, `scope=customer`, `iss`, `aud`, `iat`, `exp`, `jti` — detalhes em ADR-0064.

## Regras

1. Token com `aud=gateway` **não** autentica rotas web (cookie) nem rotas de cliente.
2. Token de cliente **não** acessa `/api/v1/admin/*` (testado em integração).
3. Authorizer HS256 do Gateway aplica-se apenas a `/api/v1/admin/*`; rotas de cliente passam pelo Gateway sem authorizer e validam RS256 na aplicação.
4. Rotação JWKS: publicar chave ativa e chaves anteriores durante sobreposição; ver ADR-0064 e testes `test_customer_jwt_auth.py`.

## Configuração (aplicação)

| Variável | Uso |
| --- | --- |
| `SECRET_KEY` / `ACCESS_TOKEN_SECRET` | HS256 admin/web/gateway |
| `CUSTOMER_JWT_JWKS_URL` | URL HTTPS do JWKS |
| `CUSTOMER_JWT_ISSUER` | Issuer esperado |
| `CUSTOMER_JWT_AUDIENCE` | Default `auto-shop-api` |

Em local, JWKS vazio desabilita rotas de cliente até configurar emissor de teste.

## Consequências

- Documentação e runbooks devem nomear explicitamente qual JWT usar em cada chamada.
- Novas audiências exigem novo ADR e alteração coordenada em Gateway, Lambda e FastAPI.
