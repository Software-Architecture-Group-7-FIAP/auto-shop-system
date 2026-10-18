# ADR-0064: Autenticação de cliente por CPF com JWT

- **Status:** Proposto
- **Data:** 2026-10-14
- **Issue de referência:** [#64 — F3-P1-02: Autenticar cliente por CPF na Function Serverless](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/issues/64)
- **Escopo:** decisão e implementação da emissão de JWT para clientes e das fronteiras entre repositórios. As pendências de contrato continuam nas issues de implementação.

## Contexto

A issue #64 prevê autenticar o cliente por CPF em uma Function Serverless, consultar o cliente e seu status, e emitir um JWT de curta duração apenas para clientes ativos. A issue também exige que dados pessoais não sejam incluídos nos claims nem expostos em logs, e aponta a necessidade de assinatura assimétrica e publicação de chaves via JWKS.

O projeto atual contém a aplicação FastAPI, seu domínio e as migrations. A issue #63 introduziu o status ativo/inativo do cliente. O fluxo administrativo existente usa autenticação própria e deve continuar separado da autenticação de clientes.

Os requisitos de entrega descritos em **13SOAT - Fase 3 - Tech Challenge.pdf** pedem repositórios separados para a Lambda, a infraestrutura Kubernetes, a infraestrutura do banco gerenciado e a aplicação principal. Este registro mantém a issue #64 como trilha de trabalho e centraliza as decisões e referências de implementação.

## Decisão proposta

Separar os artefatos gradualmente, sem duplicar o domínio ou as migrations do cliente:

| Repositório | Responsabilidade planejada |
| --- | --- |
| `lambda-auth` | Lambda de autenticação, caso de uso, adapters, testes, empacotamento e stack serverless próprio. Consulta cliente/status com credencial de banco somente leitura. |
| `k8s-infra` | Infraestrutura Kubernetes e integração com os componentes compartilhados de entrada/API Gateway, incluindo rotas e ambientes, alinhada com seus responsáveis. |
| `database-infra` | Banco gerenciado, rede/conectividade e gestão das credenciais de acesso ao banco. |
| `auto-shop-app` | Aplicação principal FastAPI e frontend. O repositório atual continua como origem até a separação gradual; domínio, schema e migrations permanecem sob responsabilidade da aplicação. |

A Lambda não será uma nova autoridade para o schema do cliente. Ela usará um port de consulta e um adapter de persistência próprio, mantendo dependências de AWS e banco fora das regras de domínio. A aplicação principal continua responsável por validar JWT de cliente nas rotas correspondentes; a autenticação administrativa atual permanece isolada, sem fallback entre os mecanismos.

## Contrato de autenticação planejado

- `POST /auth/customer/token` recebe CPF. A Function valida o formato e os dígitos localmente antes de consultar o banco.
- Cliente ativo recebe resposta `200` com Bearer JWT de validade de 900 segundos. `sub` identifica o cliente por ID interno; o payload contém somente `sub`, `principal_type`, `scope`, `iss`, `aud`, `iat`, `exp` e `jti`.
- CPF inválido não gera consulta ao banco. Cliente inexistente e cliente inativo têm a mesma resposta pública, sem permitir distinguir os casos.
- O token é assinado com RS256 usando chave assimétrica no AWS KMS. A chave pública é publicada em `GET /.well-known/jwks.json`; `kid`, emissor e audiência são configurados, não codificados no código.
- A publicação JWKS mantém as chaves necessárias para validar tokens ainda dentro da validade durante uma rotação. Nenhum CPF, nome, e-mail, telefone, segredo ou token completo deve ser escrito em logs.
- Falha de dependência retorna erro genérico sem detalhes internos. Limitação de chamadas deve reduzir tentativas abusivas sem registrar o CPF.

Os valores concretos de `iss`, `aud`, `principal_type`, `scope`, política de rate limit e códigos HTTP além do sucesso permanecem pendentes de alinhamento com o grupo. Como comportamento inicial proposto, CPF inválido retorna `422`, cliente inexistente/inativo retorna `401`, falha de banco/assinatura retorna `503` e excesso de chamadas retorna `429`, sempre com mensagens que não revelem dados do cliente.

A inativação impede novas emissões. Tokens já emitidos continuam válidos até expirarem, por no máximo 900 segundos; revogação imediata não faz parte deste fluxo inicial.

## Salvaguarda para AWS

A integração AWS pode ser preparada no código, na configuração e nos pipelines, usando mocks e validações locais. **Não** criar recursos, chaves KMS, secrets ou infraestrutura; não aplicar Terraform, fazer deploy nem executar chamadas que possam gerar cobrança antes de validação explícita do usuário.

Antes de qualquer etapa potencialmente cobrável, apresentar para validação a conta AWS, região, ambiente, recursos envolvidos e estimativa de custo. Se uma verificação depender de credenciais ou chamadas à AWS, interromper e pedir validação antes de executá-la. Após autorização, começar por homologação e reportar o resultado; produção requer validação própria antes do deploy.

## Dependências e itens pendentes

- Confirmação pelo grupo do contrato de JWT, em especial valores de emissor/audiência, política de autorização e comportamento HTTP.
- Alinhamento com os responsáveis pelos repositórios de infraestrutura para integração ao API Gateway compartilhado e acesso ao banco.
- A issue #63/status de cliente é pré-requisito de domínio; #65 integra o validador FastAPI e #68 valida o fluxo integrado.
- O CPF é identificador público e, por si só, não prova posse de identidade. O uso acadêmico inicial é CPF-only; OTP ou outra prova de posse deve ser avaliada antes de uso em produção.

## Histórico de implementação

Manter esta tabela atualizada quando houver implementação. Registrar links de issue/PR, ambiente e resultado; nunca incluir CPF, tokens, credenciais, ARNs sensíveis ou outros segredos.

| Data | Issue/PR | Repositório | Marco / resultado |
| --- | --- | --- | --- |
| 2026-10-18 | [#1 — bootstrap](https://github.com/Software-Architecture-Group-7-FIAP/lambda-auth/issues/1), [PR #4](https://github.com/Software-Architecture-Group-7-FIAP/lambda-auth/pull/4), branch `codex/issue-1-bootstrap`, commits `f1827d3` e `a5e7bf0` | `lambda-auth` | Estrutura Python 3.12, handler API Gateway v1/v2, health check, CI de qualidade e testes offline; o segundo commit corrige o pin de checkout do CI. |
| 2026-10-18 | [#2 — autenticação CPF/JWT](https://github.com/Software-Architecture-Group-7-FIAP/lambda-auth/issues/2), [PR #5](https://github.com/Software-Architecture-Group-7-FIAP/lambda-auth/pull/5), branch `codex/issue-2-cpf-jwt`, commits `8729fd0` e `da9cfbb` | `lambda-auth` | Validação local de CPF, busca somente cliente ativo, emissão RS256 e JWKS com KMS, credencial PostgreSQL lida do Secrets Manager. Issuer/audience e escolha KMS versus secret externo seguem pendentes de confirmação do grupo. |
| 2026-10-18 | [#3 — preparação de infraestrutura](https://github.com/Software-Architecture-Group-7-FIAP/lambda-auth/issues/3), [PR #6](https://github.com/Software-Architecture-Group-7-FIAP/lambda-auth/pull/6), branch `codex/issue-3-infra-preparation`, commits `c08012c`, `743edf4` e `2a16319` | `lambda-auth` | Terraform para Lambda/IAM/logs, validação estática no CI e timeouts/retries limitados para clientes AWS. Nenhuma chamada ou recurso AWS foi usado. Validação local: 58 testes, 95,38% de cobertura, Ruff, `terraform fmt`, `init -backend=false` e `terraform validate`. Estimativa numérica de custo aguarda região, conta e volume aprovados. |

## Critérios de validação da implementação

- Testar localmente a validação de CPF, ausência de consulta em CPF inválido, cliente inexistente/inativo, emissão e claims exatos, expiração, publicação JWKS e rotação de chaves, usando banco/KMS simulados.
- Testar contrato da Lambda e, na integração posterior, validar que a API FastAPI aceita o JWT de cliente sem alterar o fluxo administrativo.
- Manter testes de autenticação sem dados pessoais reais; verificar que logs e respostas de erro não revelem CPF, token, segredo ou detalhes internos.
- Nenhum deploy ou provisionamento AWS ocorre antes da validação descrita na salvaguarda acima.
