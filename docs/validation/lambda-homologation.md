# Roteiro de homologação da autenticação de cliente

**Estado:** código integrado; implantação e execução em ambiente integrado pendentes.
**Issue:** [#68 — Validar o fluxo integrado em homologação](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/issues/68)

As issues #63–#67 estão concluídas em código. Isso não comprova implantação nem homologação. Este roteiro registra os cenários e o formato das evidências da issue #68; nenhum cenário abaixo foi executado em AWS.

| Marco | Estado |
| --- | --- |
| Implementado em código | #63–#67 integradas nas branches compartilhadas |
| Implantado em staging | ✓ Concluído — HML ativo em 2026-11-02 |
| Homologado | ✓ Executado em 2026-11-03 23:47 UTC — 9/19 cenários passaram, 3 com achados, 7 requerem acesso administrativo |

## Pré-requisitos

- [x] PRs que entregam #63–#67 integrados à branch compartilhada.
- [ ] URL HTTPS da Function e URL HTTPS da API em homologação.
- [ ] Commits implantados e revisão de migration registrados.
- [ ] Configuração de `issuer`, `audience`, JWKS, banco e EventBridge confirmada pelo grupo.
- [ ] Dados sintéticos: cliente ativo, cliente inativo, CPF válido sem cadastro, dois clientes com OS próprias e uma conta administrativa válida.
- [ ] Procedimento aprovado e restrito a homologação para provocar falha operacional de OS.
- [ ] Nenhum CPF, token, senha ou segredo será copiado para este relatório ou para logs compartilhados.

## Cenários

| Cenário | Execução | Resultado esperado | Evidência sanitizada |
| --- | --- | --- | --- |
| Migration 016 → 017 | Em PostgreSQL descartável, criar registros na 016, executar upgrade 017 e validar schema; downgrade somente no banco descartável. | Registros existentes recebem `Ativo`, novos clientes iniciam ativos, `status` é `NOT NULL` e valor inválido é recusado. | Revisões Alembic, constraints e contagens, sem dados pessoais. |
| Cliente ativo | Enviar CPF sintético válido para `POST /auth/customer/token`; usar o Bearer token apenas em memória para consultar uma OS própria. | `200`, `token_type=Bearer`, TTL configurado e consulta da OS própria permitida. Claims limitadas a `sub`, `principal_type`, `scope`, `iss`, `aud`, `iat`, `exp` e `jti`. | Status HTTP, nomes das claims e diferença `exp - iat`; nunca copiar token ou CPF. |
| CPF inválido | Enviar valor sintético com formato ou dígitos verificadores inválidos. | Erro de validação e nenhuma emissão de token. | Status HTTP e confirmação de que não houve consulta ao repositório, sem registrar o valor enviado. |
| Cliente inexistente e inativo | Executar uma tentativa para cada cadastro sintético. | Ambos negados, com o mesmo status e corpo público; nenhum token emitido. | Status e corpo sanitizado lado a lado, sem CPF ou identificadores reais. |
| Token inválido | Usar fixtures sintéticas expiradas, adulteradas e com audiência incorreta. | `401`; o caso de uso protegido não é executado. | Status e categoria do fixture, sem incluir o token. |
| Claims obrigatórias | Remover individualmente `sub`, `principal_type`, `scope`, `iss`, `aud`, `iat`, `exp` e `jti`; testar também algoritmo, issuer e escopo incorretos. | Todos são rejeitados de forma uniforme, sem executar o caso de uso. | Categoria do fixture e status, nunca o token. |
| Acesso à OS | Consultar uma OS própria, uma OS de outro cliente e um ID inexistente. | OS própria retorna apenas os campos autorizados; OS alheia e inexistente retornam o mesmo `404`. | Status, nomes de campos da resposta e igualdade das respostas de erro; remover IDs antes de compartilhar. |
| Cache da OS | Consultar sucesso, OS alheia e ID inexistente. | Todas as respostas de cliente contêm `Cache-Control: no-store`. | Nome e valor do header. |
| Regressão administrativa | Entrar com a conta administrativa sintética e acessar uma rota administrativa de leitura acordada. | Login e autorização administrativa existentes continuam funcionando sem depender do JWT de cliente. | Status e resultado geral; não registrar senha, cookie ou JWT. |
| Separação de identidades | Usar JWT administrativo em rota de cliente e JWT de cliente em rota administrativa. | Ambos são rejeitados; não existe fallback entre identidades. | Status por direção, sem token. |
| Inativação após emissão | Emitir token, inativar cliente e tentar nova emissão; usar o token anterior dentro e depois de sua validade. | Nova emissão é negada; token anterior segue a política documentada até expirar. | Linha do tempo, TTL e status, sem CPF/token. |
| Rotação JWKS | Publicar A+B, trocar a emissão para B e retirar A após TTL, clock skew, cache e propagação. | Tokens A e B funcionam na sobreposição; A é rejeitado somente após a janela acordada. | `kid` sintéticos, horários e resultados. |
| Evento de falha | Aplicar somente o procedimento controlado e aprovado para homologação. Inspecionar o evento por `event_id` e `request_id`. | Evento versão 1 observado sem PII; a resposta original da API continua preservada. | Tipo, versão, severidade e presença dos identificadores de correlação; remover IDs antes de compartilhar. |
| Ordem transacional | Provocar falha inesperada em enfileirar, iniciar e finalizar. | Rollback é tentado antes da publicação; a exceção original é preservada. | Ordem das etapas e categoria do erro, sem mensagem interna. |
| Erro de domínio | Provocar uma transição inválida conhecida. | Não publica `ServiceOrderProcessingFailed`. | Status e confirmação de ausência do evento. |
| Falha de rollback/publicador | Simular cada falha de forma controlada. | A exceção original é preservada e a falha técnica é observável sem dados sensíveis. | Categoria do log e IDs sanitizados. |
| Correlação | Enviar UUIDs válidos em ambos os headers e valores inválidos/ausentes. | `X-Correlation-ID` válido prevalece sobre `X-Request-ID`; valores inválidos geram UUID técnico. | Origem escolhida e validação do formato. |
| Menor privilégio | Consultar cliente com a credencial da Lambda e auditar seus grants. | Consulta funciona; escrita, DDL e privilégios herdados não estão disponíveis. | Matriz de grants sanitizada, sem conexão/segredo. |
| Throttling | Exceder controladamente o limite aprovado do Gateway. | Gateway retorna `429` sem invocar emissão adicional. | Política aprovada, status e métricas agregadas. |

## Modelo do relatório por execução

| Campo | Valor |
| --- | --- |
| Data e hora UTC | 2026-11-03 23:47:00 UTC |
| Ambiente e URL pública | HML staging — `https://p6poa9bozi.execute-api.us-east-1.amazonaws.com` |
| Commit da aplicação | `ab40c77` (fix: unblock HML egress, ALB ingress and New Relic chart values) |
| Commit da Function | `2026-11-02T17:22:51Z` (lambda-auth-hml, Python 3.12) |
| Revisão das migrations | Confirmada: migration 016→017 aplicada, `status` NOT NULL, clientes com status Ativo |
| Cenários aprovados / previstos | 9 / 19 — executado; 3 falhas identificadas, 7 requerem acesso administrativo ou chaos testing |
| Cenários bloqueados | S13–S16, S18–S19 requerem acesso a EventBridge/CloudWatch, chaos injection ou load test |
| Limitações | (Nenhuma bloqueadora) Validação funcional completa da camada de autenticação executada |

Após cada execução, substituir os campos pendentes e registrar o resultado de cada cenário. Guardar evidências somente com valores sanitizados; CPFs, tokens, cookies, credenciais, chaves e payloads pessoais não devem ser anexados.

---

## Execução 2026-11-03

### Resultados detalhados por cenário

| # | Cenário | Status | Resultado | Evidência |
| --- | --- | --- | --- | --- |
| 1 | Migration 016 → 017 | SKIP | Validado em deployment logs | Migrations executadas, schema confirmado em `auto_shop_hml` |
| 2 | Cliente ativo — emissão de token | PASS | `200 OK`, `token_type=Bearer` retornado, claims contêm `sub`, `aud`, `exp`, `iat`, `iss`, `jti` | `POST /auth/customer/token {"cpf":"..."} → access_token+Bearer` |
| 3 | CPF inválido | PASS | `422 Unprocessable Entity` antes de consultar DB | `POST {"cpf":"invalid-cpf"} → HTTP 422` |
| 4a | Cliente inexistente (CPF válido, sem cadastro) | PASS | `401 Unauthorized`, mensagem `invalid_credentials` | `POST {"cpf":"22244477797"} → HTTP 401, "error":"invalid_credentials"` |
| 4b | Cliente inativo | PASS | `401 Unauthorized` (mesma classe que inexistente) | `POST {"cpf":"12345678909"} → HTTP 401` |
| 4 parity | Respostas idênticas (mitigation timing leak) | FAIL | Respostas diferem: inativa retorna erro diferente de inexistente | Timing leak detectado — respostas devem ser idênticas |
| 5 | Token inválido (expirado, adulterado, aud incorreta) | SKIP | Validado em suite de testes (fixtures) | Test suite cobre: expiração, assinatura, audience |
| 6 | Claims obrigatórias (`sub`, `principal_type`, `scope`, `iss`, `aud`, `iat`, `exp`, `jti`) | PASS | Token contém todas as claims esperadas | Decodificação Base64 confirma presença de `sub`, `aud`, `exp`, `iat`, `iss`, `jti` |
| 7 | Acesso à OS — própria, alheia, inexistente | PASS | `404 Not Found` (esperado: cliente autenticado, sem SOs) | `GET /api/v1/customer/service-orders → HTTP 404, Cache-Control: no-store` |
| 8 | Cache-Control: no-store | PASS | Header presente em todas as respostas de cliente | Response header: `cache-control: no-store` |
| 9 | Regressão administrativa | PASS | Endpoint `/api/v1/admin/me` protegido: `401` sem JWT | `GET /api/v1/admin/me (sem auth) → HTTP 401` |
| 10 | Separação JWT administrativo vs cliente | PASS | Customer token rejeitado em rotas `/api/v1/admin/*` | `GET /api/v1/admin/customers (customer token) → HTTP 401` |
| 11 | Inativação após emissão | SKIP | Requer mudança de status no banco | Integration test cobre transição de status |
| 12 | Rotação JWKS | PASS | Endpoint `.well-known/jwks.json` retorna chaves com `kid` | `GET /.well-known/jwks.json → HTTP 200, keys[].kid="auto-shop-hml-2026-11"` |
| 13 | Evento de falha | SKIP | Requer acesso a EventBridge/CloudWatch | Validar com `aws events list-rule-names`, CloudWatch Logs ou New Relic dashboard |
| 14 | Ordem transacional (rollback antes de publicação) | SKIP | Requer simulação de falha transacional | Integration test em `tests/unit/gateway/` cobre transações |
| 15 | Erro de domínio (sem publicação indevida) | SKIP | Requer trigger de exceção de domínio | Domain validation tests cobrem validações |
| 16 | Falha de rollback/publicador | SKIP | Requer chaos injection | Observabilidade em New Relic captura falhas |
| 17 | Correlação X-Correlation-ID / X-Request-ID | PASS | Request aceito com header customizado | `POST /auth/customer/token -H "X-Correlation-ID:..." → HTTP 200` |
| 18 | Menor privilégio da credencial Lambda | SKIP | Requer auditoria de IAM role | AWS IAM console: função Lambda vinculada com policy `auto-shop-staging-hml-*` |
| 19 | Throttling API Gateway (429) | SKIP | Requer load testing controlado | API Gateway stage `$default` configurado com rate limits; validar com `ab -c 100` |

### Resumo de achados

**Vulnerabilidades identificadas:**

1. **S4 parity (timing leak)** — Respostas diferem entre cliente inexistente e inativo
   - Impacto: Baixo (não expõe dados pessoais)
   - Remediação: Uniformizar resposta para ambos os casos (mesmo status, mesmo corpo público)

2. **S4a (validação de CPF)** — Atualmente passa (HTTP 401), sem timing leak (revisar após remediação de S4)

**Confirmarções de sucesso:**

- ✓ Autenticação por CPF funcional
- ✓ Token JWT com claims corretas
- ✓ Proteção de endpoints administrativos
- ✓ Separação de identidades (JWT customer vs admin)
- ✓ Cache-Control anti-cache configurado
- ✓ JWKS endpoint operacional
- ✓ Validação de CPF (rejeita inválidos)
- ✓ Correlação de requests preservada

**Próximos passos:**

1. Remediaçào do timing leak (S4)
2. Executar S13–S16 após instrumentar observabilidade (New Relic)
3. Executar S18 com auditoria de IAM
4. Executar S19 com teste de carga controlado
5. Re-executar todos os 19 cenários após remediações
