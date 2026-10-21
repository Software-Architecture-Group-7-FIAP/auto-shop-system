# Roteiro de homologação da autenticação de cliente

**Estado:** preparado; execução pendente de ambiente integrado.
**Issue:** [#68 — Validar o fluxo integrado em homologação](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/issues/68)

Este roteiro registra os cenários e o formato das evidências. A execução só começa quando a equipe disponibilizar homologação, dados sintéticos e a forma aprovada de provocar uma falha. Hoje essas dependências incluem as issues #76, #85 e #87. Nenhum cenário abaixo foi executado em AWS.

## Pré-requisitos

- [ ] PRs que entregam #64–#67 integrados à branch compartilhada.
- [ ] URL HTTPS da Function e URL HTTPS da API em homologação.
- [ ] Commits implantados e revisão de migration registrados.
- [ ] Configuração de `issuer`, `audience`, JWKS, banco e EventBridge confirmada pelo grupo.
- [ ] Dados sintéticos: cliente ativo, cliente inativo, CPF válido sem cadastro, dois clientes com OS próprias e uma conta administrativa válida.
- [ ] Procedimento aprovado e restrito a homologação para provocar falha operacional de OS.
- [ ] Nenhum CPF, token, senha ou segredo será copiado para este relatório ou para logs compartilhados.

## Cenários

| Cenário | Execução | Resultado esperado | Evidência sanitizada |
| --- | --- | --- | --- |
| Cliente ativo | Enviar CPF sintético válido para `POST /auth/customer/token`; usar o Bearer token apenas em memória para consultar uma OS própria. | `200`, `token_type=Bearer`, TTL configurado e consulta da OS própria permitida. Claims limitadas a `sub`, `principal_type`, `scope`, `iss`, `aud`, `iat`, `exp` e `jti`. | Status HTTP, nomes das claims e diferença `exp - iat`; nunca copiar token ou CPF. |
| CPF inválido | Enviar valor sintético com formato ou dígitos verificadores inválidos. | Erro de validação e nenhuma emissão de token. | Status HTTP e confirmação de que não houve consulta ao repositório, sem registrar o valor enviado. |
| Cliente inexistente e inativo | Executar uma tentativa para cada cadastro sintético. | Ambos negados, com o mesmo status e corpo público; nenhum token emitido. | Status e corpo sanitizado lado a lado, sem CPF ou identificadores reais. |
| Token inválido | Usar fixtures sintéticas expiradas, adulteradas e com audiência incorreta. | `401`; o caso de uso protegido não é executado. | Status e categoria do fixture, sem incluir o token. |
| Acesso à OS | Consultar uma OS própria, uma OS de outro cliente e um ID inexistente. | OS própria retorna apenas os campos autorizados; OS alheia e inexistente retornam o mesmo `404`. | Status, nomes de campos da resposta e igualdade das respostas de erro; remover IDs antes de compartilhar. |
| Regressão administrativa | Entrar com a conta administrativa sintética e acessar uma rota administrativa de leitura acordada. | Login e autorização administrativa existentes continuam funcionando sem depender do JWT de cliente. | Status e resultado geral; não registrar senha, cookie ou JWT. |
| Evento de falha | Aplicar somente o procedimento controlado e aprovado para homologação. Inspecionar o evento por `event_id` e `request_id`. | Evento versão 1 observado sem PII; a resposta original da API continua preservada. | Tipo, versão, severidade e presença dos identificadores de correlação; remover IDs antes de compartilhar. |

## Modelo do relatório por execução

| Campo | Valor |
| --- | --- |
| Data e hora UTC | Não executado |
| Ambiente e URL pública | Pendente da equipe de infraestrutura |
| Commit da aplicação | Pendente do deploy |
| Commit da Function | Pendente do deploy |
| Revisão das migrations | Pendente do ambiente |
| Cenários aprovados / executados | 0 / 0 — não executado |
| Cenários bloqueados | Todos — homologação integrada indisponível |
| Limitações | #64–#67 aguardam integração; #76, #85 e #87 estão abertas |

Após cada execução, substituir os campos pendentes e registrar o resultado de cada cenário. Guardar evidências somente com valores sanitizados; CPFs, tokens, cookies, credenciais, chaves e payloads pessoais não devem ser anexados.
