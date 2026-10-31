# Roteiro de homologação da autenticação de cliente

**Estado:** código integrado; implantação e execução em ambiente integrado pendentes.
**Issue:** [#68 — Validar o fluxo integrado em homologação](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/issues/68)

As issues #63–#67 estão concluídas em código. Isso não comprova implantação nem homologação. Este roteiro registra os cenários e o formato das evidências da issue #68; nenhum cenário abaixo foi executado em AWS.

| Marco | Estado |
| --- | --- |
| Implementado em código | #63–#67 integradas nas branches compartilhadas |
| Implantado em staging | Pendente de #76, #85, #87 e configuração integrada |
| Homologado | Pendente da execução e revisão deste roteiro (#68) |

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
| Data e hora UTC | Não executado |
| Ambiente e URL pública | Pendente da equipe de infraestrutura |
| Commit da aplicação | Pendente do deploy |
| Commit da Function | Pendente do deploy |
| Revisão das migrations | Pendente do ambiente |
| Cenários aprovados / previstos | 0 / 19 — não executado |
| Cenários bloqueados | Todos — homologação integrada indisponível |
| Limitações | #63–#67 concluídas em código; deploy/configuração dependem de #76, #85 e #87 |

Após cada execução, substituir os campos pendentes e registrar o resultado de cada cenário. Guardar evidências somente com valores sanitizados; CPFs, tokens, cookies, credenciais, chaves e payloads pessoais não devem ser anexados.
