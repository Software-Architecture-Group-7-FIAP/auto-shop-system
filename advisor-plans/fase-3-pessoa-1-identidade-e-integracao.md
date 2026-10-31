# Fase 3 — Pessoa 1: identidade, autorização e integração funcional

| Campo | Referência |
| --- | --- |
| Responsável atual | Gustavo, que assume as frentes das Pessoas 1 e 2 |
| Tipo | Documento de execução e acompanhamento; não representa nova ADR aprovada |
| Estado | Núcleo funcional implementado; homologação integrada pendente |
| Data do retrato | 22/10/2026, America/Sao_Paulo |
| Repositórios | `auto-shop-system` e `lambda-auth` |
| Rastreabilidade | Issues da aplicação #63–#68; plano integrado #98 |
| Bases remotas da auditoria | Aplicação `develop/9009a18b`; Lambda `main/5a75c5d` |

Este documento detalha a frente original da Pessoa 1 para execução por Gustavo. O estado foi extraído da auditoria consolidada; não houve nova consulta ao GitHub nesta separação documental. Antes de implementar, conferir mudanças posteriores aos commits de referência.

Documentos relacionados: [relatório consolidado](relatorio-fase-3-status-e-divisao-2-devs.md), [Pessoa 2 — plataforma e CI/CD](fase-3-pessoa-2-plataforma-e-cicd.md) e [Pessoa 3 — observabilidade e entrega](fase-3-pessoa-3-observabilidade-e-entrega.md).

## 1. Objetivo e fronteiras

Entregar o fluxo em que um cliente ativo autentica por CPF, recebe um JWT temporário e consulta somente a própria OS. Uma falha operacional inesperada no processamento deve produzir um evento técnico seguro, preservando a resposta original da aplicação.

O escopo inclui domínio/status de cliente, contrato de autenticação, emissor Lambda, validador JWT, autorização por propriedade, produtor de eventos, testes e homologação funcional. O schema do cliente e suas migrations permanecem na aplicação principal; a Lambda apenas consulta as informações necessárias.

Provisionamento de rede/EKS/RDS/KMS, Gateway, IAM, entrega de secrets e CD pertencem à frente Pessoa 2, também assumida por Gustavo. Essa separação técnica permanece para evitar misturar regra funcional com infraestrutura. O consumidor de eventos, notificações, dashboards e pacote final pertencem à Pessoa 3.

## 2. Decisões já documentadas

As referências arquiteturais são [ADR-0064 — autenticação por CPF/JWT](../docs/architecture/decisions/ADR-0064-autenticacao-cliente-cpf-jwt.md) e [ADR-0066/0067 — OS do cliente e evento de falha](../docs/architecture/decisions/ADR-0066-0067-os-cliente-e-evento-de-falha.md). Preservar atualizações locais existentes ao reconciliar esses documentos.

| Decisão herdada | Consequência de implementação |
| --- | --- |
| CPF-only no escopo acadêmico de homologação | CPF identifica o cadastro; não é prova forte de posse de identidade. Evolução de identidade é decisão futura, não novo requisito imposto por este documento. |
| RS256 com assinatura KMS e publicação JWKS | Emissor e consumidor compartilham contrato de issuer, audience, kid e chave pública. |
| TTL máximo inicial de 900 segundos | A inativação bloqueia novas emissões; tokens anteriores permanecem válidos até expirar. |
| Identidade de cliente distinta de administrador | Não fazer fallback entre autenticação administrativa e JWT de cliente. |
| Consulta da OS limitada ao cliente do token | IDs de cliente informados pelo solicitante não definem autorização. |
| Mesmo 404 para OS inexistente ou alheia | Evitar revelar existência/propriedade de recursos por diferença de resposta. |
| Evento best-effort, sem outbox nesta entrega | A publicação pode se perder; falha do publicador não substitui a exceção original. |
| Limitação de tentativas antes de expor autenticação | Gateway e configuração operacional são dependências da Pessoa 2. |

## 3. Situação das entregas #63–#68

| Entrega | Situação na auditoria | Evidência e conclusão permitida |
| --- | --- | --- |
| [#63 — status de acesso](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/issues/63) | Concluído em código | [PR #107](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/pull/107) integrado em `develop`: domínio, migration 017, persistência e alteração administrativa. |
| [#64 — CPF na Lambda](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/issues/64) | Concluído em código | [Lambda PR #7](https://github.com/Software-Architecture-Group-7-FIAP/lambda-auth/pull/7) e [#9](https://github.com/Software-Architecture-Group-7-FIAP/lambda-auth/pull/9), em `main`: validação prévia do CPF, cliente ativo e respostas uniformes. |
| [#65 — validação JWT](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/issues/65) | Concluído em código | [PR #111](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/pull/111), em `develop`: RS256/JWKS, claims obrigatórias e `/customer/me`. |
| [#66 — própria OS](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/issues/66) | Concluído em código | Mesmo PR #111: consulta por OS e cliente, DTO restrito, mesmo 404 e respostas sem cache. |
| [#67 — evento operacional](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/issues/67) | Concluído em código no escopo definido | Mesmo PR #111: falhas inesperadas ao enfileirar, iniciar ou finalizar OS; rollback anterior à publicação. |
| [#68 — homologação](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/issues/68) | Pendente | Runbook preparado, sem evidências de execução AWS preenchidas. |
| Rotação JWKS com sobreposição | Parcial | Endpoint publica uma chave; falta publicar simultaneamente antiga e nova durante transição. |

As issues #63–#67 estavam fechadas. Isso comprova o fechamento funcional registrado, não implantação em homologação. A `main` da aplicação ainda estava em `7cfcc94`, anterior aos incrementos; a promoção precisa ocorrer pelo fluxo de PR/revisão.

### 3.1 Referências de implementação

| Área | Arquivos examinados na auditoria |
| --- | --- |
| Status | `src/domain/customer/entity.py:17` e `:78`; `alembic/versions/017_customer_access_status.py:38`; `src/api/routers/customers.py:111` |
| Validação JWT e principal | `src/infrastructure/auth/customer_jwt.py:42`; `src/api/dependencies.py:29` e `:67`; `src/api/routers/customer_identity.py:11` |
| Autorização e DTO | `src/infrastructure/persistence/service_order_repository.py:47`; `src/api/routers/customer_service_orders.py:23`; `src/main.py:96` |
| Eventos | `src/application/services/execution_service.py:147`; `src/infrastructure/events/eventbridge.py:25` |
| Lambda | `src/lambda_auth/application/authentication.py:30`; `src/lambda_auth/adapters/postgres_customer_repository.py:30`; `src/lambda_auth/adapters/kms_token_signer.py:34` e `:77` |

Os caminhos da última linha pertencem ao repositório `lambda-auth`; os demais, à aplicação. Linhas são referências do retrato auditado e podem mudar após novos commits.

## 4. Contratos funcionais que devem permanecer alinhados

### 4.1 Endpoints e acesso

| Endpoint | Entrada/autorização | Saída ou garantia |
| --- | --- | --- |
| `POST /auth/customer/token` | CPF validado localmente antes da consulta | Cliente ativo recebe `access_token`, `token_type=Bearer` e `expires_in`; inexistente/inativo têm resposta pública equivalente. |
| `GET /.well-known/jwks.json` | Publicação de material público | JWKS com `kid` compatível com o token; nunca publicar material privado. |
| `GET /api/v1/customer/me` | Bearer JWT de cliente | Verificação mínima da identidade técnica, sem depender de identidade administrativa. |
| `GET /api/v1/customer/service-orders/{service_order_id}` | Cliente derivado do `sub` validado | Resumo autorizado da própria OS, `Cache-Control: no-store` e mesmo 404 para recurso inexistente/alheio. |
| Alteração de status administrativa | Autenticação e autorização administrativa | Apenas `Ativo`/`Inativo`, sem ampliar contratos públicos para expor status indevidamente. |

O Gateway existente atendia `POST /auth/login` administrativo e authorizer HS256. Não equivale às rotas de cliente RS256 acima; a integração precisa de entrega própria da Pessoa 2.

### 4.2 JWT e ciclo de chave

Claims obrigatórias: `sub`, `principal_type`, `scope`, `iss`, `aud`, `iat`, `exp` e `jti`. Cabeçalho com `alg=RS256` e `kid`. O `sub` usa o ID interno do cliente; `principal_type=customer`, `scope=customer` e audiência inicial `auto-shop-api`. Não incluir CPF, nome, contato ou outro dado pessoal.

O validador deve continuar rejeitando token sem expiração, expirado, adulterado, com algoritmo não permitido, emissor/audiência incorretos ou principal/escopo incompatíveis. Configuração ausente e indisponibilidade de JWKS precisam continuar distinguíveis internamente de credenciais inválidas, sem expor detalhes sensíveis ao cliente.

A rotação pendente deve prever publicação da chave nova antes de sua adoção para emissão, coexistência antiga/nova durante a validade dos tokens e consideração do cache JWKS e tolerância de relógio configurados. Retirar a chave antiga somente após a janela acordada. Testar tokens dos dois `kid` durante a transição.

### 4.3 Evento de falha

| Campo | Finalidade |
| --- | --- |
| `event_id` | Identificador único para rastreabilidade e deduplicação do consumidor |
| `event_type` | `ServiceOrderProcessingFailed` |
| `event_version` | Versão 1 do contrato |
| `occurred_at` | Instante da ocorrência |
| `request_id` | Correlação técnica UUID válida |
| `service_order_id` | OS afetada |
| `severity` | Severidade operacional |

Publicar somente em falhas inesperadas dos casos de uso de enfileirar, iniciar e finalizar OS. Erros de domínio esperados não geram evento. Tentar rollback antes da publicação e preservar a exceção original mesmo que rollback/publicador falhem. Não anexar mensagem sensível de exceção, SQL, CPF, contato ou token.

`X-Correlation-ID` UUID válido tem precedência sobre `X-Request-ID`; entradas ausentes/inválidas são substituídas por UUID técnico. Pessoa 3 deve manter a mesma semântica na instrumentação e no consumidor.

## 5. Backlog restante em ordem de execução

### P1-01 — reconciliar base, contratos e rastreabilidade

Comparar branches locais com os commits de referência e trabalho posterior antes de editar. Atualizar a checklist original para separar código concluído de homologação pendente. Corrigir o runbook que ainda afirma que #64–#67 aguardam integração, pois já estavam em `develop`. Reconciliar ADRs com os PRs recentes sem sobrescrever alterações locais.

**Dependência:** nenhuma infraestrutura para preparar documentação. **Aceite:** matrizes de status, branches e bloqueios concordam; a #68 permanece aberta até execução. **Evidência:** PR documental com revisão cruzada e links das entregas já integradas.

### P1-02 — completar rotação JWKS

Definir configuração de chaves ativa e anteriores; implementar publicação multichave no adapter e testes de transição. Registrar duração da sobreposição levando em conta TTL, cache e relógio. Se a equipe optar por limitação temporária, registrar desvio explícito e seu aceite; este documento não aprova automaticamente essa redução de escopo.

**Dependência:** contrato de chave com Pessoa 2; testes com KMS simulado podem avançar antes da cloud. **Aceite:** JWTs antigos e novos válidos são aceitos durante sobreposição, e a retirada posterior é testada. **Evidência:** testes, PR revisado e procedimento de rotação.

### P1-03 — integrar configuração funcional ao ambiente

Entregar à Pessoa 2 nomes de variáveis, endpoints, claims e permissões necessárias. Conferir issuer, audience, kid, JWKS e event bus efetivamente recebidos pelo workload e pela Lambda. As configurações existiam no Compose, mas faltavam nos manifests/infra locais auditados. Validar usuário de banco da Lambda com leitura restrita às tabelas/colunas necessárias.

**Dependência:** #76, #79, #85 e plataforma de staging #87; KMS/secrets/Gateway/EventBridge da Pessoa 2. **Aceite:** autenticação e consulta usam o mesmo contrato de ambiente; a Lambda não pode executar escrita com sua credencial. **Evidência:** configuração sanitizada e verificação de grants, sem connection strings ou secrets.

### P1-04 — executar e encerrar homologação #68

Usar o [runbook de homologação](../docs/validation/lambda-homologation.md). Registrar ambiente, data/hora, commits da aplicação/Lambda, versão de pacote/imagem e migration aplicada. Executar a matriz abaixo com dados sintéticos e forma controlada de provocar falha operacional.

**Dependência:** staging disponível, limitação de tentativas ativa no Gateway, banco e chaves alinhados; Pessoa 3 preparada para localizar eventos/logs. **Aceite:** todos os cenários obrigatórios aprovados com evidências reproduzíveis. **Evidência:** relatório preenchido anexado/vinculado à #68 e revisão da dupla.

## 6. Matriz de testes e critérios de aceite

| Cenário | Resultado esperado | Evidência sanitizada |
| --- | --- | --- |
| Migration e novos clientes | Existentes recebem default/backfill; novos começam ativos; status inválido rejeitado | Revisão da migration, testes e resultado de schema sem dados pessoais |
| CPF inválido | Rejeitado antes de consultar banco ou assinar | Teste com doubles e contagem de chamadas |
| Cliente ativo | Recebe JWT com claims permitidas e TTL dentro do máximo | Status HTTP, nomes das claims e duração; nunca token completo |
| Cliente inexistente/inativo | Sem emissão, respostas públicas equivalentes | Comparação de status/corpo sem CPF |
| JWT inválido | Expirado, adulterado, issuer/audience/escopo/algoritmo incorretos são rejeitados | Categoria do caso, status HTTP e confirmação de caso de uso não executado |
| Separação de identidades | JWT de cliente não ganha acesso administrativo e regressão admin permanece funcional | Status e descrição do teste, sem senha/cookie/token |
| OS própria | Retorna somente DTO autorizado e `no-store` | Nomes dos campos e headers |
| OS de outro cliente/inexistente | Mesmo 404 em ambos | Comparação sanitizada de resposta |
| Inativação após emissão | Novas emissões negadas; token anterior segue a política até expirar | Linha do tempo técnica sem token/CPF |
| Falha operacional de execução | Rollback antecede publicação; um evento v1 preserva erro original | Ordem verificada em testes e evento sem dados pessoais |
| Erro de domínio | Não publica evento operacional | Teste com fake publicador |
| Falha do publicador | Exceção original preservada; falha técnica observável | Teste e log sanitizado |
| Rotação JWKS | Chaves antiga/nova coexistem e retirada respeita janela | Testes de ambos os `kid` e execução registrada |

Na aplicação, executar o comando de CI `poetry run pytest --cov=src --cov-report=term-missing --cov-fail-under=80`, além dos controles de segurança vigentes. Na Lambda, executar `python -m pytest --cov=lambda_auth --cov-report=term-missing --cov-fail-under=80`, `python -m ruff check .` e `python -m ruff format --check .` no ambiente do projeto.

A auditoria registrou [CI da aplicação](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/actions/runs/39774667654) com **514 testes e 90,42%**, e [CI da Lambda](https://github.com/Software-Architecture-Group-7-FIAP/lambda-auth/actions/runs/39869147838) com **74 testes e 95,38%**. São evidências dos commits auditados, não execução de homologação ou garantia de cobertura integral em cada módulo crítico.

## 7. Entregas entre as frentes

| Pessoa 1 fornece | Destinatário | Retorno necessário |
| --- | --- | --- |
| Contrato JWT/JWKS, TTL, endpoints e configuração | Pessoa 2 | URLs HTTPS, KMS/kid, secrets, conectividade e deploy alinhados |
| Necessidade de consulta de cliente e ownership de migrations | Pessoa 2 | Banco com migration aplicada e grants de leitura comprovados |
| Contrato de evento e publisher | Pessoa 2 | Event bus e permissão restrita de publicação; destino/consumidor provisionáveis |
| Semântica UUID e campos seguros | Pessoa 3 | Instrumentação consistente e busca por correlação |
| Eventos de teste e método de falha controlada | Pessoa 3 | Consumidor/notificação e evidência operacional |
| Resultado funcional da #68 | Pessoa 3 | Inclusão na documentação, vídeo e PDF final |

Mesmo sendo a mesma pessoa nas frentes 1 e 2, registrar esses contratos evita concluir uma tarefa funcional sem seus pré-requisitos de ambiente. PRs de implementação permanecem sujeitos à revisão do outro desenvolvedor.

## 8. Riscos e limites de conclusão

Os riscos principais são divergência entre emissor/validador, exposição da rota sem throttling, falha de acesso ao banco/chaves, rotação sem sobreposição e ausência de configuração no Kubernetes. Revisar essas interfaces antes de investigar regressão em regras funcionais já testadas.

O modelo best-effort pode perder eventos. A homologação deve demonstrar seu comportamento e observabilidade, preservando a limitação documentada. A aprovação do produtor não equivale à entrega de consumidor/alerta da Pessoa 3.

Não considerar código em branch antiga ou suíte com mocks como prova de integração cloud. O CI local/remote e o relatório de homologação devem indicar explicitamente seus respectivos ambientes e commits.

## 9. Checklist de conclusão da Pessoa 1

- [x] Status Ativo/Inativo, migration e alteração administrativa implementados.
- [x] Lambda valida CPF, cliente ativo e emite JWT RS256/KMS em código.
- [x] JWKS de chave única disponível em código.
- [x] Validação de JWT de cliente sem fallback administrativo implementada.
- [x] Consulta limitada à própria OS com DTO reduzido e `no-store` implementada.
- [x] Produtor de evento v1 best-effort implementado no escopo de execução.
- [x] Testes/CI dos commits auditados aprovados acima da meta global de 80%.
- [ ] Runbook e ADRs reconciliados com a integração já realizada.
- [ ] Rotação multichave implementada/testada ou desvio formal rastreado.
- [ ] Emissor/validador e runtime configurados no mesmo ambiente.
- [ ] Credencial de banco da Lambda com leitura restrita comprovada.
- [ ] Gateway de cliente integrado com limitação de tentativas.
- [ ] Homologação #68 executada e revisada, com regressão administrativa.
- [ ] Falha de OS observada em integração com Pessoa 3.
- [ ] Evidências sanitizadas entregues e promoção da aplicação rastreada por PR.

**Conclusão da frente:** o código principal está entregue. O próximo resultado é provar o funcionamento integrado, completar a lacuna de rotação e fornecer evidências de aceite, aproveitando a plataforma que Gustavo assume como Pessoa 2.
