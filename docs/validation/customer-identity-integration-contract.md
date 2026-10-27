# Contrato de integração da identidade de cliente

Este documento é o gate sanitizado entre as Pessoas 1, 2 e 3. Valores específicos de conta, ARNs, segredos, CPFs e tokens não são registrados aqui.

## Contrato funcional

| Item | Contrato |
| --- | --- |
| Emissão | `POST /auth/customer/token`; CPF inválido `422`, cliente ausente/inativo `401` equivalente, dependência indisponível `503` |
| Chaves | `GET /.well-known/jwks.json`; RS256, `kid`, somente material público |
| API de cliente | `GET /api/v1/customer/me` e `GET /api/v1/customer/service-orders/{id}` |
| Claims | `sub`, `principal_type=customer`, `scope=customer`, `iss`, `aud=auto-shop-api`, `iat`, `exp`, `jti` |
| Cache | Rotas de cliente: `Cache-Control: no-store`; JWKS: cache público acordado com a janela de rotação |
| Autorização | Cliente vem exclusivamente do `sub`; OS alheia e inexistente retornam o mesmo `404` |
| Erros | `401` para credencial/cliente recusado, `404` uniforme para OS, `422` para entrada inválida, `429` no Gateway e `503` para dependência indisponível |
| Evento | Bus em `SERVICE_ORDER_EVENT_BUS_NAME`, source `auto-shop.service-orders`, detail type `ServiceOrderProcessingFailed` e payload v1 com `event_id`, `event_type`, `event_version`, `occurred_at`, `request_id`, `service_order_id`, `severity` |

## Configuração por ambiente

O emissor usa `JWT_ISSUER`, `JWT_AUDIENCE`, `JWT_TTL_SECONDS`, `JWT_KID`, `JWT_KMS_KEY_ID` e `JWT_ADDITIONAL_PUBLIC_KEYS_JSON`. A aplicação usa `CUSTOMER_JWT_JWKS_URL`, `CUSTOMER_JWT_ISSUER`, `CUSTOMER_JWT_AUDIENCE`, `CUSTOMER_JWT_CLOCK_SKEW_SECONDS`, `CUSTOMER_JWT_JWKS_TIMEOUT_SECONDS`, `CUSTOMER_JWT_JWKS_CACHE_SECONDS` e `SERVICE_ORDER_EVENT_BUS_NAME`.

Issuer e audience devem ser idênticos nos dois runtimes. URLs usam HTTPS em staging/produção. Valores públicos ficam em ConfigMap; conexão, credenciais e material privado permanecem em Secret/KMS.

Em staging e produção, a aplicação recusa a inicialização se faltar JWKS HTTPS, issuer, audience ou nome do event bus. A composição do fluxo de execução conecta o publisher EventBridge ao bus configurado.

## CORS para clientes de navegador — pendente

A Lambda de identidade ainda não atende preflight `OPTIONS` nem inclui cabeçalhos CORS nas respostas de emissão e JWKS. Portanto, o contrato atual não garante chamadas feitas diretamente por navegadores.

Placeholder da configuração da Lambda, a definir por ambiente: `CUSTOMER_AUTH_CORS_ALLOWED_ORIGINS=<origens-do-frontend-a-definir>`. Esse valor não deve ser implantado literalmente.

Antes de habilitar clientes de navegador, retomar este item na homologação #68: definir as origens permitidas para cada ambiente, implementar `OPTIONS` no API Gateway e CORS nas respostas da Lambda, e validar preflight, origem permitida e origem recusada.

## Banco e migration

A aplicação é dona do schema e deve aplicar ao menos a migration Alembic 017. A Lambda recebe usuário próprio com `CONNECT`, `USAGE` e `SELECT` mínimo para `customers(id,status)` e `customer_documents(customer_id,document)`, sem escrita, DDL ou herança privilegiada.

## Responsabilidades e gates

| Responsável | Entrega | Gate |
| --- | --- | --- |
| Pessoa 1 | Código, testes, contrato JWT/JWKS, DTO e produtor do evento | Suítes locais/CI aprovadas e contrato congelado |
| Pessoa 2 | Gateway/throttling, KMS, secrets, rede, grants, runtime e `events:PutEvents` limitado ao bus | Configuração sanitizada, conectividade e permissões verificadas |
| Pessoa 3 | Consumidor, busca por correlação, alerta e evidência operacional | Evento sintético localizado sem PII |

Este repositório não declara a identidade IAM do workload EKS. A Pessoa 2 deve vincular o ServiceAccount da aplicação a uma role exclusiva com `events:PutEvents` restrito ao bus configurado; nome e ARN entram apenas na configuração segura do ambiente.

A homologação #68 começa somente depois dos três gates. CI/mocks não substituem a execução em staging.
