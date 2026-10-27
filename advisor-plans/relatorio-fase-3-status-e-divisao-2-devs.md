# Fase 3 — relatório de situação e reorganização para dois desenvolvedores

Data de referência: **22 de outubro de 2026**, America/Sao_Paulo.

> **Atualização de escopo — 2026-10-27:** este relatório preserva a auditoria original. Para decisões vigentes sobre conta Paid/créditos, ambientes lógicos, CloudFront/domínio/WAF, acesso EKS e bootstrap do banco, consulte o ADR-0071 e `revisao-fase-2-status-2026-10-27.md`. Os documentos de auditoria não são autorização para provisionar recursos.

Detalhamento separado por responsabilidade: [Pessoa 1 — identidade e integração](fase-3-pessoa-1-identidade-e-integracao.md), [Pessoa 2 — plataforma e CI/CD](fase-3-pessoa-2-plataforma-e-cicd.md) e [Pessoa 3 — observabilidade e entrega](fase-3-pessoa-3-observabilidade-e-entrega.md). Gustavo assume as Pessoas 1 e 2; o outro desenvolvedor assume a Pessoa 3. Este relatório preserva a consolidação da auditoria que originou os três documentos.

Base de requisitos: [divisão original para três pessoas](../docs/contexts/tasks/fase-3-divisao-3-pessoas.md). Base de rastreabilidade: [plano integrado #98](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/issues/98), issues, PRs, código local e consultas atuais à API do GitHub.

## 1. Parecer executivo

**O núcleo funcional da Pessoa 1 está implementado e testado, mas a Fase 3 ainda não está concluída.** As issues #63–#67 foram encerradas e suas implementações estão integradas: aplicação em `develop`, autenticação em `lambda-auth/main`. A homologação integrada #68 continua pendente.

**O maior volume restante é a plataforma da Pessoa 2.** Já existem manifests Kubernetes, Terraform para workloads, Terraform de Gateway, CI, publicação de imagem e esqueleto de CD. Isso não equivale a EKS, RDS, autenticação de cliente no Gateway e deploy cloud funcionando. A execução recente de CD publicou imagem, mas pulou o deploy.

**A frente da Pessoa 3 está parcialmente iniciada.** Há ADRs e documentação, correlação básica e um PR aberto para logs JSON. Não foi comprovada a entrega de APM, traces distribuídos, dashboards, alertas, consumidor de notificações e pacote final.

Com dois desenvolvedores, a recomendação é:

- **Você:** assumir Pessoas 1 + 2; preservar as funcionalidades prontas e concentrar a execução em infraestrutura, integração, CD e homologação.
- **Outro desenvolvedor:** manter Pessoa 3; continuar observabilidade, notificações, documentação e entrega final. Fornecer apoio/revisão nos componentes de Gateway e CI/CD que já desenvolveu.

Não há base para atribuir um percentual global confiável: as issues possuem tamanhos diferentes e várias encerradas representam código pronto, sem aceite operacional.

## 2. Método e limites da conclusão

Classificações usadas:

| Situação | Significado |
| --- | --- |
| Concluído em código | Implementação encontrada, integrada à branch indicada e sustentada por testes/CI. |
| Parcial | Parte implementada; faltam requisitos, integração ou evidência operacional. |
| Pendente | Critério não atendido pelas evidências consultadas. |
| Não comprovado | Pode existir fora dos repositórios, mas não há evidência suficiente para atestar. |

Foram examinados os dois repositórios locais solicitados, os históricos relevantes de PRs, issues #63–#95 e #98, execuções de Actions, jobs de deploy, políticas de branch, ambientes GitHub e inventário de repositórios da organização. O repositório privado de banco foi consultado para verificar se existia conteúdo reutilizável.

Não foram acessados serviços AWS nem feitos deploys, provisionamento, alterações de issues, configurações de GitHub, commits ou merges. Ausência de prova nos repositórios não comprova inexistência de recursos em uma conta AWS. Para homologação, prevalece a falta de evidência de execução, reforçada pelo runbook e pelos jobs pulados.

Esta é uma análise de aderência à Fase 3, e não uma auditoria integral de todos os requisitos antigos, dependências do frontend ou vulnerabilidades de toda a aplicação.

## 3. Bases de código e diferenças entre local e GitHub

| Repositório / referência | Commit verificado | Observação |
| --- | --- | --- |
| Aplicação, checkout local `F3P1-02-customer-access-events` | `e740df3861a87c962051139b47a883576acfebbe` | Branch funcional anterior aos merges recentes de CI/CD. |
| Aplicação, `develop` remoto consultado | `9009a18b773621c4fcd0fc1ddb4a7ff2781be3e9` | Inclui funcionalidades de cliente, Gateway, CI, CD e política de branches. |
| Aplicação, `main` remoto | `7cfcc948f7aa441ae1599ebf2874faf61d9626a5` | Continua na entrega anterior; os incrementos da Fase 3 ainda precisam de promoção revisada. |
| Lambda, checkout e `main` locais | `26cca0a06bcdbc4ada21d8b90d00cda5715d7f7f` | Não contém o último reforço de preparação da infraestrutura. |
| Lambda, `main` remoto consultado | `5a75c5d08e3ba7792ccab5a325a614ad72b97a80` | Inclui PR #10, com proteção de CI sem credenciais AWS e documentação adicional. |

O checkout local da aplicação possuía alterações prévias nos dois ADRs, o documento de divisão não rastreado e diretórios temporários. Foram preservados. A árvore da Lambda estava limpa. A análise remota foi necessária para não classificar trabalho já integrado como ausente.

## 4. Repositórios exigidos

| Componente esperado | Evidência atual | Situação |
| --- | --- | --- |
| Aplicação | [auto-shop-system](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system) | Existente, com código, CI e publicação de imagem. |
| Autenticação | [lambda-auth](https://github.com/Software-Architecture-Group-7-FIAP/lambda-auth) | Existente, com código, testes e IaC preparatória. |
| Banco | [auto-shop-db-cloud-infra](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-db-cloud-infra) | Repositório privado criado em 15/10; vazio, tamanho zero, sem commits, branch `main`, issues ou execuções de Actions. A API de árvore retorna `409: Git Repository is empty`. |
| Cluster/plataforma | `k8s-infra` ou equivalente | Nenhum repositório correspondente encontrado no inventário da organização acessível nesta consulta. |

Portanto, **dois repositórios possuem implementação; um terceiro existe apenas como contêiner vazio; o quarto não foi localizado**. A busca inicial do conector retornou apenas os dois públicos; a listagem autenticada da organização revelou o banco privado. Confirmar o nome final do repositório de banco antes de criar outro duplicado.

## 5. Pessoa 1 — o que está concluído e o que falta

| Entrega original | Situação | Evidências e limite do aceite |
| --- | --- | --- |
| #63 — status Ativo/Inativo | Concluído em código | [PR #107](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/pull/107), integrado em `develop`. Domínio, persistência, migration 017 com backfill/default e alteração administrativa autenticada. |
| #64 — autenticação de cliente por CPF | Concluído em código | [Lambda PR #7](https://github.com/Software-Architecture-Group-7-FIAP/lambda-auth/pull/7) e [#9](https://github.com/Software-Architecture-Group-7-FIAP/lambda-auth/pull/9), integrados em `main`; valida CPF antes da consulta, exige cliente ativo e responde uniformemente para inexistente/inativo. |
| JWT RS256/KMS, claims e TTL | Concluído em código para emissão | `sub` interno, `principal_type=customer`, `scope=customer`, `iss`, `aud`, `iat`, `exp`, `jti`, `kid`; TTL máximo de 900 s. Sem dados pessoais nas claims. Configuração final depende do ambiente. |
| JWKS | Parcial em relação ao plano completo | Endpoint implementado, mas publica uma única chave. A janela de rotação com chave antiga + nova simultâneas ainda não está implementada. |
| #65 — validação do JWT na aplicação | Concluído em código | [PR #111](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/pull/111), em `develop`. Validação RS256/JWKS, claims obrigatórias, issuer/audience/expiração, identidade de cliente separada de admin e `GET /api/v1/customer/me`. |
| #66 — consulta da própria OS | Concluído em código | Mesmo PR #111. Consulta limitada por ID da OS e cliente autenticado; DTO reduzido; mesmo 404 para OS alheia/inexistente; respostas sem cache. |
| #67 — evento de falha | Concluído em código no escopo acordado | Porta e adapter EventBridge; evento v1 em falhas inesperadas ao enfileirar, iniciar ou finalizar OS; rollback anterior à publicação, preservação da falha original e entrega best-effort. |
| #68 — homologação integrada | Pendente | [Issue #68](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/issues/68) aberta. Runbook pronto; nenhum resultado AWS preenchido. |

Referências locais verificadas para rastrear o código:

- `src/domain/customer/entity.py:17` e `:78`; `alembic/versions/017_customer_access_status.py:38`; `src/api/routers/customers.py:111`.
- `src/infrastructure/auth/customer_jwt.py:42`; `src/api/dependencies.py:29` e `:67`; `src/api/routers/customer_identity.py:11`.
- `src/infrastructure/persistence/service_order_repository.py:47`; `src/api/routers/customer_service_orders.py:23`; `src/main.py:96`.
- `src/application/services/execution_service.py:147`; `src/infrastructure/events/eventbridge.py:25`.
- Lambda: `src/lambda_auth/application/authentication.py:30`; `src/lambda_auth/adapters/postgres_customer_repository.py:30`; `src/lambda_auth/adapters/kms_token_signer.py:34` e `:77`.

Pendências para fechar a frente funcional:

1. Implantar Lambda, aplicação, banco e JWKS com o mesmo contrato `iss/aud/kid`.
2. Assegurar credencial PostgreSQL da Lambda realmente restrita às leituras necessárias. A consulta é parametrizada e usa TLS, mas privilégios reais não são garantidos pelo código Python.
3. Completar a rotação JWKS ou registrar formalmente a limitação aceita para a entrega; não marcar o requisito original como integralmente atendido enquanto publicar só uma chave.
4. Levar configurações JWT/JWKS e EventBridge para a implantação Kubernetes/Terraform. Foram encontradas no Compose, mas não nos manifests/infra locais auditados.
5. Executar #68 e registrar commits implantados, migration, cenários e evidências sanitizadas.

O evento best-effort sem outbox e a validade de tokens já emitidos até a expiração são decisões documentadas. Não foram tratados como defeitos novos. O produtor de eventos não substitui o consumidor de notificações da Pessoa 3.

## 6. Pessoa 2 — plataforma e CI/CD

### 6.1 O que já existe e deve ser reaproveitado

- `k8s/`: Deployment, Service, ConfigMap, namespace, probes, requests/limits, HPA, Ingress, Job de migrations e overlays local/staging/production.
- `infra/`: Terraform para workloads em **cluster já existente**, incluindo banco somente local quando habilitado. O próprio README informa que esse root não cria EKS, VPC, IAM nem RDS.
- `infra/aws/` e `gateway/`: implementação de Gateway administrativo, auth proxy, authorizer, WAF, throttling, TLS/domínio e logs, integrada pelo [PR #97](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/pull/97).
- Lambda `infra/terraform/`: módulo de Function, role/policy IAM e log group, integrado pelos [PRs #8](https://github.com/Software-Architecture-Group-7-FIAP/lambda-auth/pull/8) e [#10](https://github.com/Software-Architecture-Group-7-FIAP/lambda-auth/pull/10). Recebe banco/rede/KMS/secrets externos; não os provisiona.
- Aplicação [PR #99](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/pull/99): CI reorganizado e templates de workflows para outros componentes.
- Aplicação [PR #100](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/pull/100): publicação GHCR, workflows de staging/production, OIDC e script de deploy preparados.
- Aplicação [PR #109](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/pull/109): documentação/política de proteção; a configuração real também foi confirmada pela API.

### 6.2 Matriz das issues de plataforma

As issues **#69–#87 estão abertas**. O estado aberto, sozinho, não significa ausência total de código: #78, #84 e #86 já possuem partes reutilizáveis.

| Issues | Entrega | Situação técnica / trabalho restante |
| --- | --- | --- |
| #69 | Bootstrap do banco | Parcial: repositório vazio existe; faltam Terraform, README, backend, CI e proteção. |
| #70 | Bootstrap de Kubernetes | Pendente: repositório próprio não localizado. |
| #71, #72, #74 | VPC/subnets/NAT, EKS/OIDC, node groups | Pendente nas evidências: Terraform de workloads não provisiona essa fundação. |
| #73, #75 | Rede privada/SG e RDS PostgreSQL | Pendente: nenhum módulo de banco cloud entregue no repositório vazio. |
| #76 | Secrets e usuários com menor privilégio | Pendente no ambiente: separar credenciais de app, Lambda e operação; criar grants e entrega gerenciada. |
| #77 | Namespace/RBAC/quotas/NetworkPolicies | Parcial: namespace/workload existem; completar controles e provar aplicação no cluster cloud. |
| #78 | HPA | Parcial: política e smoke de escala no Kind existem; falta calibração com carga representativa e evidência em homologação. |
| #79 | Ingress/DNS/TLS cloud | Parcial: manifests e componentes Gateway/domínio preparados; integração com infraestrutura real não comprovada. |
| #80 | External Secrets Operator + IRSA | Pendente: instalar/integrar e validar acesso restrito aos secrets. |
| #81, #82 | Outputs de banco e cluster | Pendente: contratos devem sair dos módulos definitivos e alimentar consumidores/pipelines. |
| #83 | RDS Proxy | Opcional no backlog; decidir por necessidade/custo, sem bloquear a entrega obrigatória por padrão. |
| #84 | Migrations antes do Deployment | Parcial: Job e deploy em fases existem; provar execução e interrupção de rollout quando migration falhar no ambiente alvo. |
| #85 | App e Lambda conectadas ao banco | Pendente em homologação: código de acesso existe, conectividade privada, TLS e grants reais ainda precisam de validação. |
| #86 | Imagem por digest e rollback | Parcial: workflow publica tag `sha-<7 caracteres>`, sem output de digest; script aceita referência, mas não automatiza rollback. A documentação orienta redeploy manual da tag anterior. Completar pin por digest e reversão automatizada/testada. |
| #87 | Staging completo | Pendente e principal marco bloqueador da homologação, observabilidade cloud e aceite. |
| #88 | API Gateway | Issue fechada, mas integração Fase 3 de cliente ainda parcial; ver seção seguinte. |
| #89 | CI/CD nos quatro repositórios | Parcial: CI da aplicação e da Lambda existe; templates não comprovam quatro pipelines independentes operacionais. |
| #90 | Build/push/deploy/OIDC | Parcial: build/push comprovado; deploy real de staging pulado. |
| #91 | Proteção de branches | Parcial no conjunto: aplicação protegida, Lambda sem proteção e repos de infra sem entrega correspondente. |

Mensageria também permanece uma dependência explícita: provisionar EventBridge, publicação restrita da aplicação, regra/target, permissões do consumidor, retry e DLQ quando aplicáveis. O adapter Python não cria esses recursos. O backlog #69–#95 não dá a esse trabalho e ao consumidor a mesma visibilidade das demais entregas; vinculá-los explicitamente ao plano #98.

### 6.3 Gateway administrativo ainda não atende o fluxo de cliente

O Gateway atual implementa `POST /auth/login` com usuário/senha e authorizer **HS256** administrativo. O cliente da Fase 3 utiliza `POST /auth/customer/token`, **RS256/KMS/JWKS** e audiência `auto-shop-api`.

Em `infra/aws/api_gateway.tf`, existem recursos para auth/login, admin, public e health; não foram encontradas as rotas de cliente e JWKS requeridas para ligar o fluxo da Fase 3. `gateway/README.md` confirma a finalidade administrativa das Lambdas existentes.

É necessário integrar:

- `POST /auth/customer/token` → Lambda `lambda-auth`, com limitação de tentativas antes da exposição.
- `GET /.well-known/jwks.json` → emissor/publicação de chaves.
- `/api/v1/customer/*` → aplicação, preservando Bearer e validação RS256 na API.
- Correlação ponta a ponta e respostas de erro/429/CORS/TLS conforme contrato por ambiente.

Se houver authorizer adicional no Gateway para cliente, ele deve respeitar RS256/JWKS e as claims de cliente. O authorizer administrativo atual não deve ser reutilizado como se validasse esses tokens.

### 6.4 O que a execução de CD comprova

Execução consultada: [CD Staging 39774667796](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/actions/runs/39774667796), commit `9009a18b`.

| Job | Resultado |
| --- | --- |
| `build-push / build-push` | Sucesso; build e publicação GHCR executados. |
| `deploy-staging-skipped` | Sucesso; registra explicitamente o bloqueio até #87. |
| `deploy-staging` | **Skipped**; deploy não executado. |

O workflow em `develop` usa a condição `vars.DEPLOY_STAGING_ENABLED == 'true'`. A consulta a GitHub Environments retornou lista vazia. Portanto, **workflow verde não comprova staging implantado**. Faltam ambiente, role OIDC, região, cluster e execução real com smoke/rollback.

Referências remotas para reprodução: `.github/workflows/cd-staging.yml:24`, `.github/workflows/reusable-build-push.yml:34`, `k8s/scripts/deploy.sh` e `.github/CD.md`, seção de produção. O script já ordena foundation → migration → espera da migration → app → rollout → ingress → smoke; preservar essa sequência ao completar o deploy.

Na Lambda, a CI monta o pacote e valida código/IaC, inclusive impedindo credenciais AWS nesta fase. Ainda faltam publicação persistente/versionada do artefato, implantação, promoção, smoke e rollback. A [issue lambda-auth #3](https://github.com/Software-Architecture-Group-7-FIAP/lambda-auth/issues/3) continua aberta após os PRs de preparação; reconciliar o escopo de preparação com a futura atividade de ativação/deploy.

### 6.5 Proteção e acesso de avaliação

- Aplicação `main` e `develop`: PR, uma aprovação, branch atualizada e sete checks obrigatórios; force push bloqueado. **`enforce_admins=false`**: a proteção não impede bypass por administradores; alinhar com a regra de não fazer commits diretos.
- Lambda `main`: `protected=false`; API de proteção retorna 404 e regras aplicáveis retornam `[]`. Não está atendendo ao requisito de branch protegida.
- Banco: vazio e sem branch principal efetiva; ainda precisa de configuração de governança e CI.
- Usuário `soat-architecture`: permissão `read` confirmada nos dois repositórios de aplicação/Lambda. Acesso aos futuros repositórios e ao banco privado deve entrar no fechamento.

## 7. Pessoa 3 — observabilidade, notificações e entrega

| Entrega | Situação atual | Restante |
| --- | --- | --- |
| #92 — Datadog/New Relic ou equivalente | Pendente de evidência | Definir ferramenta e integrar app, Lambda, cluster e banco. |
| #93 — JSON/correlação/traces | Parcial | [PR #110](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/pull/110) aberto, com CI atual verde; entrega logs JSON e correlação da API, mas declara traces/métricas posteriores. Revisar e integrar. |
| Correlação na Lambda de cliente | Pendente | Adapter HTTP local não preserva request ID/headers para correlacionar a execução; implementar contrato junto ao Gateway e app. |
| #94 — dashboards e alertas | Pendente de evidência | Painéis técnicos e de negócio, uptime, recursos, falhas e investigação por correlação. |
| Consumidor `ServiceOrderProcessingFailed` | Não localizado nas evidências | Implementar serverless, validação de versão, deduplicação, canal de notificação, retry, DLQ e alarmes. |
| #95 — documentação | Parcial | Há arquitetura anterior, schema ER e dois ADRs funcionais; completar os documentos da Fase 3 e reconciliar com o deploy efetivo. |
| Vídeo e PDF final | Não comprovados | Roteiro e vídeo de até 15 minutos; PDF único com links, evidências e acesso de avaliação. |

Dashboards a entregar: volume diário de OS; tempo médio por status; falhas de integração e processamento; latência/disponibilidade; CPU/memória Kubernetes; healthchecks/uptime; correlação ponta a ponta. Registrar fonte, período, unidade, filtros e alertas.

Documentação a completar: componentes cloud, sequências de autenticação e abertura de OS, RFCs de nuvem/banco/autenticação, ADRs de comunicação/eventos e HPA, justificativa PostgreSQL, ER/índices/consistência/performance e READMEs dos quatro repositórios com execução, testes, deploy e rollback.

O PR #110 é um avanço real, mas ainda aberto. Seu CI atual está verde no [run 39777031353](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/actions/runs/39777031353). Não usar falhas antigas da branch para descrever o estado atual.

## 8. Testes e qualidade: evidências verificadas

| Base | Resultado | Alcance |
| --- | --- | --- |
| Aplicação `develop/9009a18b`, [CI 39774667654](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/actions/runs/39774667654) | **514 testes; 90,42% de cobertura** | Logs do job consultados; Bandit sem issues e pip-audit sem vulnerabilidades conhecidas naquela execução. |
| Mesmo CI da aplicação | Jobs `gateway`, `manifests`, `terraform-k8s`, `terraform-aws`, `cluster-smoke` e `frontend` aprovados | Inclui validação de manifests/Terraform e smoke em cluster descartável; não prova operação EKS/RDS. |
| Lambda `main/5a75c5d`, [CI 39869147838](https://github.com/Software-Architecture-Group-7-FIAP/lambda-auth/actions/runs/39869147838) | **74 testes; 95,38% de cobertura**, Ruff aprovado | Qualidade e Terraform estático aprovados; dependências AWS simuladas. |
| Lambda local `26cca0a` | **70 testes; 95,38%**, Ruff lint/formatação e Terraform fmt aprovados | Executado durante esta análise. Diferença de contagem decorre do checkout anterior ao PR #10. |
| Aplicação local, subset de migration/eventos/execução | **20 testes aprovados, 5 excluídos** | Verificação direcionada. Testes HTTP e uma tentativa de subset completo foram interrompidos após ficarem sem progresso; não constituem validação integrada local. |
| Terraform validate da Lambda local | Inconclusivo | Provider AWS falhou ao responder ao carregamento de schema; não inferir erro de IaC. A CI remota atual de validação passou. |

Os percentuais superam a meta global de 80%, mas não comprovam 100% em cada módulo crítico nem ausência universal de vulnerabilidades. A CI da Lambda ainda não apresenta uma etapa de auditoria de dependências equivalente à da aplicação; incluir no padrão de qualidade dos quatro repositórios. Não foi executada uma nova auditoria externa de dependências nesta revisão.

## 9. Divergências entre planejamento, issues e implementação

1. **Checklist original da Pessoa 1 está desatualizado:** #63–#67 estão fechadas e implementadas, embora a checklist final permaneça desmarcada. Atualizar com distinção entre código e homologação.
2. **#88 fechada não significa Gateway de cliente integrado:** o fluxo atual é administrativo. Abrir follow-up ou ampliar rastreabilidade para as rotas CPF/JWKS/customer.
3. **#89/#90/#91 continuam abertas apesar dos PRs #99/#100/#109 integrados:** faz sentido manter o aceite global aberto enquanto faltarem quatro repositórios, deploy real e proteção da Lambda. Registrar os subitens já entregues para evitar retrabalho.
4. **#105/HPA fechada não comprova calibração de homologação:** o documento local `docs/issues/revisao-fase-2/F2-04-calibrar-hpa.md` registra que carga representativa e calibração continuam pendentes e orienta manter #78 aberta. Escala no Kind é uma evidência diferente.
5. **Runbook #68 contém texto antigo:** ainda diz que #64–#67 aguardam integração; já estão em `develop`. O bloqueio atual é implantação/integração do ambiente e execução dos cenários.
6. **Dois repositórios visíveis no documento não são o inventário completo atual:** há um repositório privado de banco, porém vazio.
7. **ADRs precisam incorporar o histórico mais recente:** o trabalho local contém atualizações prévias não commitadas; reconciliar PRs #7–#10 da Lambda e decisões finais de ambiente, sem sobrescrever alterações existentes.
8. **Novo ownership precisa aparecer no #98:** ele ainda distribui #69–#87 ao terceiro integrante anterior. A transferência para você deve ficar explícita; o relatório não alterou assignees automaticamente.

## 10. Nova divisão de responsabilidades

| Frente | Responsável final | Colaboração / fronteira |
| --- | --- | --- |
| Status, CPF, JWT, JWKS, autorização e produtor de eventos | Você | Outro desenvolvedor revisa contratos, logs e instrumentação. |
| Repositórios cloud, VPC, EKS, RDS, KMS, IAM e secrets | Você | Outro desenvolvedor fornece requisitos de coleta, logs e alertas. |
| Gateway, CI/CD e governança dos quatro repos | Você, por incorporar Pessoa 2 | Reaproveitar implementação existente; outro desenvolvedor apoia transição e revisão. |
| Event bus, targets, permissões e infraestrutura da notificação | Você | Contrato definido em conjunto com o consumidor. |
| Consumidor serverless e lógica de notificação | Outro desenvolvedor | Você entrega destino/permissões/rede e integra deploy de infraestrutura. |
| APM, JSON, correlação, traces, métricas, dashboards e alertas | Outro desenvolvedor | Você habilita acessos/infra e participa da integração. |
| Homologação funcional #68 e plataforma #87 | Você | Outro desenvolvedor valida telemetria/notificações e captura evidências. |
| Diagramas, RFCs, ADRs, READMEs, vídeo e PDF | Outro desenvolvedor | Você fornece/revisa conteúdo de autenticação/plataforma e participa da demonstração. |
| Revisão de PRs e aceite | Ambos | Revisão cruzada; evitar bypass administrativo. |

Essa divisão define responsáveis finais e não exige transferir todo o desenvolvimento de CI/Gateway já iniciado. A outra pessoa pode concluir uma fatia em andamento, desde que a responsabilidade pela integração e aceite da plataforma permaneça clara.

## 11. Sequência recomendada de execução

### Marco A — consolidar contratos e repositórios

**Você:** confirmar nomes dos quatro repos, inicializar o banco existente e o repo de cluster, definir ownership dos recursos compartilhados, backend remoto com estado separado por ambiente, CI e proteção. Registrar conta/região/topologia/custos e janela de ativação antes do provisionamento.

**Outro desenvolvedor, em paralelo:** concluir revisão/integração do PR #110, definir ferramenta de observabilidade, campos de logs, correlação UUID e contrato do consumidor. Atualizar #98 e matriz de responsabilidades, com revisão de vocês dois.

**Aceite:** quatro repositórios com estrutura e checks mínimos; contratos JWT, rotas, rede, secrets, eventos e outputs escritos; plano de recursos e custos revisado. Evitar criar um quinto repo apenas para renomear a aplicação: o documento aceita o `auto-shop-system` atual.

### Marco B — fundação cloud e dados

**Você:** #71–#76, #80–#82 e node groups; rede compartilhada com um único proprietário de Terraform; EKS e RDS privados; backup/criptografia; credenciais separadas; KMS e secrets para Lambda; conectividade necessária a KMS/Secrets/JWKS, sem pressupor acesso externo ilimitado.

**Outro desenvolvedor:** instrumentar Lambda/app com testes offline, implementar consumidor e seus testes, preparar coleta/dashboards como configuração e atualizar diagramas/RFCs.

**Aceite:** plano e aplicação revisados, outputs consumíveis, app e Lambda conseguem apenas os acessos autorizados; grants da Lambda comprovadamente de leitura; procedimento de backup/restauração e desligamento documentado.

### Marco C — publicação e implantação integradas

**Você:** integrar as rotas de cliente no Gateway com throttling; concluir #77/#79/#84–#86; injetar configurações JWT/eventos no Kubernetes; publicar pacote Lambda e imagem versionados; configurar GitHub Environments/OIDC; habilitar deploy apenas após pré-requisitos e executar smoke/rollback.

**Outro desenvolvedor:** instalar coleta/APM, testar correlação, integrar consumidor ao evento, configurar DLQ/retry/alarmes e carregar dados para painéis.

**Aceite:** URLs HTTPS respondem pelo Gateway, migrations precedem rollout, deploy real concluído, imagem identificada por digest, Lambda versionada e rollback demonstrado. Um job `deploy-staging-skipped` não atende este marco.

### Marco D — homologação, escala e operação

**Você:** executar #68 e #87 com clientes/OS sintéticos, regressão administrativa, tokens inválidos, IDOR e falha operacional; calibrar HPA #78 com perfil de carga e registrar resultados.

**Outro desenvolvedor:** comprovar traces/correlação, painéis técnicos e de negócio, notificação de falha, duplicidade/versão desconhecida do evento, falha do provedor, retry/DLQ e alarmes.

**Aceite:** todos os cenários têm resultado reproduzível, commits implantados e evidências sanitizadas; nenhum token/CPF/segredo é exposto. Para produção, registrar promoção e configuração próprias após homologação; não inferir entrega de produção a partir de arquivos de workflow.

### Marco E — revisão final e entrega

**Você:** revisar conteúdo técnico, conferir proteção e acesso de avaliação nos quatro repos, fechar/promover branches via PR e fornecer evidências de deploy/rollback/recuperação.

**Outro desenvolvedor:** completar #95, READMEs e diagramas finais, gravar demonstração de até 15 minutos, publicar vídeo e preparar PDF com todos os links.

**Aceite:** pacote final navegável, quatro repositórios acessíveis ao avaliador, vídeo sem dados sensíveis e checklist de cada requisito ligado à evidência.

Dependência principal: **repositórios/contratos → rede/EKS/RDS/secrets → Gateway e deploy → #87 → #68 + observabilidade integrada → pacote final**. Documentação, instrumentação e consumidor podem avançar antes do cluster. Não há dados suficientes de disponibilidade da dupla para estimar datas de entrega com responsabilidade.

## 12. Prioridades e riscos de execução

| Prioridade | Trabalho | Impacto / esforço relativo | Risco da mudança | Confiança |
| --- | --- | --- | --- | --- |
| P0 | Repos cloud e fundação EKS/RDS/secrets | Desbloqueia quase toda integração; L | Alto: custo, rede e persistência; revisar planos e restauração. | Alta quanto à lacuna documental/código. |
| P0 | Gateway CPF/JWKS/customer + configuração de runtime | Fluxo não chega ao código pronto sem isso; M/L | Médio: preservar autenticação administrativa e respostas públicas. | Alta. |
| P0 | CD real, ambientes e #87/#68 | Transforma preparação em evidência de entrega; L | Alto: migration, rollout e operação; exigir smoke/rollback. | Alta. |
| P1 | Proteção Lambda e governança uniforme | Fecha requisito explícito; S | Baixo: conferir nomes reais de checks para não bloquear PRs indevidamente. | Alta. |
| P1 | EventBridge + consumidor + alertas | Fecha caminho de falha da OS até notificação; M/L | Médio: permissões, duplicidade, indisponibilidade; manter exceção original. | Alta. |
| P1 | Telemetria/dashboards/traces | Requisito obrigatório e dependência do vídeo; L | Médio: volume, custo e sanitização; instrumentar com dados técnicos. | Alta quanto à falta de evidência. |
| P1 | Rotação JWKS multichave | Cumpre contrato original e reduz rejeição de tokens na transição; M | Médio: cache/TTL/retirada da chave; testar sobreposição. | Alta. |
| P1 | Calibração HPA e digest/rollback comprovados | Evita aceitar smoke local como operação cloud; M | Médio: capacidade e política de escala. | Alta. |
| P1 | Documentos finais e pacote | Necessário para aceite acadêmico; M/L | Baixo: manter consistência com ambientes e testes reais. | Alta. |

S = horas; M = aproximadamente um dia; L = múltiplos dias, como ordem de grandeza por frente, incluindo testes e evidências. Não somar como cronograma: existem dependências e paralelismo.

Não se recomenda reimplementar status/JWT/consulta de OS/eventos já entregues. Também não há justificativa nesta revisão para exigir outbox ou prova adicional de identidade como novo escopo de homologação: as limitações acadêmicas estão registradas nos ADRs. RDS Proxy permanece opção, não prioridade obrigatória.

## 13. Checklist de encerramento para a dupla

- [x] Status Ativo/Inativo implementado com migration e testes.
- [x] Autenticação CPF e emissão RS256/KMS implementadas na Lambda.
- [x] Validação JWT de cliente e separação administrativa implementadas na API.
- [x] Consulta apenas da própria OS e prevenção de cache implementadas.
- [x] Produtor do evento de falha implementado no escopo de execução.
- [x] CI da aplicação e da Lambda com resultados atuais aprovados.
- [x] Publicação de imagem GHCR comprovada.
- [x] Proteção da aplicação e acesso `soat-architecture` nos dois repos principais confirmados.
- [ ] Quatro repos com implementação, CI/CD e proteção.
- [ ] Governança sem bypass incompatível com a regra da equipe.
- [ ] EKS/RDS/rede/secrets/KMS e estado remoto entregues e documentados.
- [ ] Gateway integrado à autenticação e API do cliente com limitação de tentativas.
- [ ] Configuração JWT/JWKS/EventBridge nos workloads de implantação.
- [ ] JWKS com janela de rotação antiga/nova ou desvio formal aceito e rastreado.
- [ ] CD efetivo da aplicação e Lambda, smoke, digest/versão e rollback demonstrados.
- [ ] HPA calibrado e validado em homologação.
- [ ] Event bus, consumidor, retry/DLQ e notificação comprovados.
- [ ] Logs JSON, correlação, métricas e traces nos componentes integrados.
- [ ] Dashboards, uptime e alertas testados.
- [ ] #68/#87 executadas com evidências sanitizadas.
- [ ] Promoção/configuração de produção conforme critério acordado.
- [ ] Documentação, READMEs e acesso de avaliação completos nos quatro repos.
- [ ] Vídeo de até 15 minutos e PDF final preparados.

**Critério final:** a fase só está concluída quando código funcional, plataforma reproduzível e operação demonstrável estiverem comprovados conjuntamente. Hoje o código funcional é a frente mais madura; plataforma e evidências operacionais são o caminho crítico.
