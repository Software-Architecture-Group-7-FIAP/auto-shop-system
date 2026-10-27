# Fase 3 — Pessoa 2: plataforma cloud e CI/CD

## 1. Identificação e uso deste documento

| Campo | Valor |
| --- | --- |
| Responsável atual | Gustavo, assumindo as responsabilidades originais das Pessoas 1 e 2. |
| Tipo | Documento de situação, decisões herdadas e plano de execução. |
| Estado | Plataforma parcialmente preparada; implantação integrada pendente. |
| Data-base das evidências | 22/10/2026, America/Sao_Paulo. |
| Aplicação remota examinada | `develop/9009a18b773621c4fcd0fc1ddb4a7ff2781be3e9`. |
| Lambda remota examinada | `main/5a75c5d08e3ba7792ccab5a325a614ad72b97a80`. |
| Rastreabilidade | Issues #69–#91 e plano integrado #98; `lambda-auth#3`. |

Este documento separa a frente de plataforma do [relatório consolidado](relatorio-fase-3-status-e-divisao-2-devs.md). Ele reutiliza a auditoria registrada; não representa uma nova consulta ao GitHub ou à AWS. Ausência de evidência nos repositórios não comprova ausência de recursos em uma conta cloud.

> **Atualização vigente — 2026-10-27:** para conta/custos, ambientes lógicos `hml`/`prd`, acesso EKS, identidades e bootstrap DB, prevalecem ADR-0071 e `revisao-fase-2-status-2026-10-27.md`. CloudFront/S3 do Angular, domínio próprio, ACM e WAF estão mantidos no escopo. O restante abaixo preserva a fotografia da auditoria e pode conter planos substituídos; não autoriza apply.

Documentos relacionados: [Pessoa 1 — identidade e integração](fase-3-pessoa-1-identidade-e-integracao.md), [Pessoa 3 — observabilidade e entrega](fase-3-pessoa-3-observabilidade-e-entrega.md) e [divisão original](../docs/contexts/tasks/fase-3-divisao-3-pessoas.md).

Não é um novo ADR aceito. Decisões já documentadas são preservadas; escolhas ainda abertas devem ser confirmadas e registradas antes da implantação.

## 2. Resultado esperado e limites

A Pessoa 2 entrega uma plataforma reproduzível que executa a aplicação, a autenticação serverless e o banco gerenciado, com deploy automatizado, acesso restrito e evidências operacionais.

**Escopo AWS vigente para esta fase:** um único ambiente de staging/homologação, efêmero e criado apenas para integração; o desenvolvimento diário continua local. Produção, uma segunda conta AWS e promoção entre ambientes estão fora desta entrega. O dimensionamento e a topologia devem priorizar o menor custo por sessão sem declarar recursos como gratuitos.

Está no escopo: quatro repositórios, Terraform, estado remoto, VPC, EKS, node groups, RDS, IAM, KMS, Secrets Manager, Gateway, entrada TLS, HPA, migrations, EventBridge, permissões do consumidor e CI/CD.

A regra de autenticação, autorização de OS e contrato do evento pertencem à Pessoa 1. A lógica do consumidor, instrumentação, dashboards, alertas e pacote documental pertencem à Pessoa 3. A infraestrutura que permite executar esses componentes pertence à Pessoa 2.

Gustavo acumula duas frentes, mas os critérios de aceite continuam separados: código funcional pronto não substitui deploy; cluster saudável não substitui homologação do fluxo de cliente.

## 3. Inventário atual e trabalho a reaproveitar

| Repositório esperado | Situação verificada | Próxima ação |
| --- | --- | --- |
| [auto-shop-system](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system) | Código, manifests, Terraform de workloads, Gateway, CI e publicação de imagem. | Integrar ao cluster e banco gerenciados; preservar histórico e contratos. |
| [lambda-auth](https://github.com/Software-Architecture-Group-7-FIAP/lambda-auth) | Código funcional e módulo Terraform de Lambda/IAM/logs; CI sem deploy. | Completar publicação de artefato e implantação após pré-requisitos. |
| [auto-shop-db-cloud-infra](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-db-cloud-infra) | Privado, criado em 15/10, vazio; sem commits, branch principal efetiva ou pipeline. | Confirmar nome e inicializar; evitar criar outro repo de banco por duplicidade. |
| `k8s-infra` ou equivalente | Não localizado no inventário acessível da auditoria. | Criar/inicializar o repositório de plataforma acordado. |

Ativos existentes:

- `k8s/` contém namespace, ConfigMap, Deployment, Service, probes, recursos, HPA, Ingress, Job de migrations e overlays local/staging/production. O overlay de produção existente não amplia o escopo AWS desta fase e não deve ser implantado.
- `infra/` gerencia workloads em um cluster existente. Não cria EKS, VPC, IAM ou RDS. O PostgreSQL opcional desse root destina-se ao ambiente local.
- `infra/aws/` e `gateway/` contêm Gateway administrativo, proxy de login, authorizer, WAF, throttling, domínio/TLS e logs.
- `lambda-auth/infra/terraform/` cria Function, execution role/policy e log group; recebe rede, segredo e chave externos.
- PRs da aplicação [#97](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/pull/97), [#99](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/pull/99), [#100](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/pull/100) e [#109](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/pull/109) já foram integrados em `develop`.
- PRs da Lambda [#8](https://github.com/Software-Architecture-Group-7-FIAP/lambda-auth/pull/8) e [#10](https://github.com/Software-Architecture-Group-7-FIAP/lambda-auth/pull/10) entregam preparação de IaC e validação sem AWS.

Não aplicar Terraform e Kustomize aos mesmos recursos no mesmo namespace. Definir um proprietário de cada recurso por ambiente antes de extrair ou reutilizar módulos.

## 4. Matriz de situação por issue

As issues #69–#87 estavam abertas na data-base. Os estados abaixo qualificam o conteúdo encontrado, sem alterar o estado no GitHub.

| Issue | Entrega | Situação e falta para aceite |
| --- | --- | --- |
| #69 | Bootstrap do banco | Parcial: repo vazio existe; faltam IaC, README, estado, CI e governança. |
| #70 | Bootstrap de Kubernetes | Pendente: repo próprio não localizado. |
| #71 | VPC, subnets e NAT | Pendente nas fontes auditadas; definir topologia, saídas necessárias e custos. |
| #72 | EKS, IAM e OIDC | Pendente: Terraform atual pressupõe cluster existente. |
| #73 | Rede privada e SG do banco | Pendente: restringir origem a workloads e Lambda autorizados. |
| #74 | Node groups | Pendente: capacidade, atualização e limites documentados. |
| #75 | RDS PostgreSQL | Pendente: provisionamento, criptografia, backup e restauração. |
| #76 | Secrets e menor privilégio | Pendente no ambiente: usuários distintos e grants reais comprovados. |
| #77 | Namespace, RBAC, quotas e NetworkPolicies | Parcial: namespace/workload existem; completar controles cloud. |
| #78 | HPA | Parcial: política e smoke Kind existem; falta carga representativa e calibração. |
| #79 | Ingress, DNS e TLS | Parcial: manifests e recursos preparados; integração real não comprovada. |
| #80 | External Secrets Operator e IRSA | Pendente de implementação/validação integrada. |
| #81 | Outputs do banco | Pendente: contratos do módulo definitivo, sem expor credenciais. |
| #82 | Outputs do cluster | Pendente: contratos consumíveis por deploy e observabilidade. |
| #83 | RDS Proxy | Opcional: decidir por necessidade e custo; não bloquear entrega por padrão. |
| #84 | Migrations antes do Deployment | Parcial: Job e ordem de deploy existem; provar bloqueio em falha. |
| #85 | App e Lambda conectadas ao banco | Pendente em homologação: rede, TLS e privilégios reais. |
| #86 | Digest e rollback automatizado | Parcial: tag SHA publicada; faltam pin por digest e reversão automatizada/testada. |
| #87 | Staging demonstrável | Pendente: principal bloqueador de homologação e operação integrada. |
| #88 | API Gateway | Fechada; entrega administrativa integrada, fluxo de cliente ainda incompleto. |
| #89 | CI/CD nos quatro repos | Parcial: dois CIs reais e templates; quatro pipelines não comprovados. |
| #90 | PR, build/push, deploy e OIDC | Parcial: publicação comprovada; deploy staging pulado. |
| #91 | Branches protegidas | Parcial: aplicação protegida; Lambda e infra não atendem ao conjunto. |
| `lambda-auth#3` | Preparação IaC sem AWS | Preparação integrada, issue aberta; separar aceite preparatório de futura ativação. |

EventBridge, regra/target, permissões de publicação/consumo, retry e DLQ também precisam de rastreabilidade explícita no [plano #98](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/issues/98). O produtor Python da Pessoa 1 não provisiona esses recursos.

## 5. Evidências que limitam a conclusão operacional

### 5.1 Gateway atual e autenticação de cliente

O Gateway atual atende `POST /auth/login` administrativo, com usuário/senha e authorizer HS256. O fluxo de cliente exige `POST /auth/customer/token`, RS256/KMS/JWKS e audiência `auto-shop-api`.

`infra/aws/api_gateway.tf` declara auth/login, admin, public e health. A auditoria não encontrou as rotas de token CPF, JWKS e API do cliente. A finalidade administrativa é confirmada em `gateway/README.md`.

| Rota a integrar | Destino / contrato de aceite |
| --- | --- |
| `POST /auth/customer/token` | Lambda de cliente; validação CPF; throttling antes de exposição; 429 demonstrado. |
| `GET /.well-known/jwks.json` | Publicação de chaves do emissor; acessível pelo validador; cache/rotação alinhados. |
| `/api/v1/customer/*` | Serviço da aplicação; Bearer preservado; validação RS256 e propriedade da OS na API. |

Preservar o fluxo administrativo. Caso seja criado authorizer de cliente no Gateway, seu contrato deve ser RS256/JWKS e não o mecanismo HS256 administrativo.

### 5.2 CD verde com deploy pulado

No [run CD Staging 39774667796](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/actions/runs/39774667796), o job `build-push / build-push` passou, `deploy-staging-skipped` passou e `deploy-staging` ficou **skipped**.

O gate `.github/workflows/cd-staging.yml:24` depende de `DEPLOY_STAGING_ENABLED == 'true'`. GitHub Environments retornou lista vazia na consulta registrada. Logo, a evidência comprova publicação GHCR, sem comprovar implantação.

`reusable-build-push.yml` publica `sha-<7 caracteres>` e retorna tag/reference. Essa referência não é um digest. `deploy.sh` aceita referência e ordena foundation → migration → espera → app → rollout → ingress → smoke; o rollback descrito em `.github/CD.md` usa redeploy manual da tag anterior.

### 5.3 Proteções e qualidade

- Aplicação `main` e `develop`: PR, uma aprovação, branch atualizada e sete checks obrigatórios. `enforce_admins=false` ainda permite bypass administrativo.
- Lambda `main`: sem proteção na data-base; endpoint de proteção retornou 404 e regras aplicáveis `[]`.
- `soat-architecture` tinha acesso `read` nos dois repos principais; falta validar o conjunto com infra.
- [CI da aplicação 39774667654](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/actions/runs/39774667654): 514 testes, 90,42%; Bandit/pip-audit aprovados naquela execução, além de Terraform/manifests/smoke Kind/frontend.
- [CI Lambda 39869147838](https://github.com/Software-Architecture-Group-7-FIAP/lambda-auth/actions/runs/39869147838): 74 testes, 95,38%, Ruff e validação estática Terraform aprovados; sem deploy AWS.

## 6. Decisões herdadas e escolhas a fechar

Decisões registradas que a plataforma deve respeitar:

- Aplicação FastAPI em Kubernetes; PostgreSQL gerenciado; quatro repositórios e Terraform.
- Domínio e migrations continuam na aplicação; Lambda consulta clientes, sem assumir o schema.
- JWT de cliente RS256/KMS, JWKS, audiência `auto-shop-api`, TTL máximo de 900 segundos e sem PII.
- Evento `ServiceOrderProcessingFailed` v1, best-effort, sem outbox inicial; preservar exceção original.
- Homologar uma infraestrutura AWS efêmera com namespaces/databases/stages lógicos `hml` e `prd`; não há conta, cluster ou RDS separado para produção nem alta disponibilidade de produção nesta fase. Logs/evidências devem ser sanitizados.
- Domínio próprio `api.oficina-workshop.com.br` (API Gateway) e `app.oficina-workshop.com.br`/`app-hml.oficina-workshop.com.br` (CloudFront + S3), DNS no Registro.br, ACM e WAF permanecem no escopo confirmado em 2026-10-27; integração HTTP privada VPC Link–ALB (TLS até o ALB adiado). hml e prd usam namespaces/databases/stages lógicos na mesma infraestrutura efêmera, sem CodeBuild.
- Ativação AWS ainda depende de custo completo, validação do bootstrap seguro, revisão dos plans, procedimento de desligamento e autorização explícita por sessão, conforme ADR-0064.

## Decisões fechadas e validações restantes — atualização 2026-10-27

As decisões abaixo substituem a lista de escolhas abertas da auditoria de 22/10. O desenho não autoriza apply nem deploy.

| Tema | Decisão vigente | Validação operacional pendente |
| --- | --- | --- |
| Repos e ownership | `auto-shop-system`, `lambda-auth`, `database-infra` e `k8s-infra`; propriedade de rede/EKS no `k8s-infra`, RDS em `database-infra`, Gateway/EventBridge no `auto-shop-system`. | Confirmar contratos de IDs/ARNs e permissões entre repositórios no plan e no smoke. |
| Topologia e saída | Uma infraestrutura AWS efêmera `staging`, namespaces/databases/stages lógicos `hml`/`prd`; endpoint EKS público e privado com IAM access entries; sem CodeBuild. | Validar IPs, rotas, políticas de rede, Pod Identity, TLS/CA e teardown. |
| Capacidade e custo | Dois nodes On-Demand para a Sessão 1; quotas aprovadas de 16 vCPU On-Demand e 32 Spot. Conta Paid com US$ 140 em créditos concedidos e saldo desconhecido. | Recalcular o escopo completo, incluindo CloudFront/S3, domínio, ACM e WAF Regional + `CLOUDFRONT`; revalidar sizing e saldo. |
| Estado Terraform | Backend remoto separado por repositório, S3 com lock nativo; um ambiente AWS efêmero. | Verificar acesso/locking e revisar cada plan antes de sessão autorizada. |
| Domínio e entrada | Domínio próprio, Angular via CloudFront/S3, ACM e WAF permanecem no escopo; API via API Gateway Regional + WAF Regional; WAF CloudFront usa escopo `CLOUDFRONT`; VPC Link → ALB usa HTTP privado. | Conferir DNS existente, emitir certificados, testar CORS, throttling, rotas e 429 após autorização de sessão. |
| Banco e bootstrap | Três identidades por database; init containers `aws-cli` + `postgres:16`, `PutSecretValue` e arquivos/segredos em tmpfs. | Resolver seguro `asm-exec`, idempotência, grants pós-migration, restauração e smoke. |
| Deploy e recuperação | GitHub Actions com OIDC; pipeline da aplicação publica imagem por digest; não há runner privado CodeBuild. | Fechar rollback, compatibilidade de migrations, deploy Lambda e fluxo de sessão. |

## 7. Plano de execução ordenado

### P2-01 — consolidar repositórios, contratos e governança

Confirmar os nomes dos quatro repos e inicializar os dois de infra. Transferir a responsabilidade #69–#87 para Gustavo no planejamento. Reaproveitar templates CI, configurar proteção com checks que realmente existam e definir revisão cruzada na dupla.

Especificar inputs/outputs e proprietário de cada recurso compartilhado. Registrar a única conta/região/topologia de staging, custo por sessão, alertas de orçamento, janela de ativação e teardown. A criação dos documentos não autoriza executar infraestrutura cobrável.

**Aceite:** quatro repos com conteúdo, README, CI e branches protegidas; plano revisado; ausência de recursos com ownership duplicado; pendências de ativação explicitamente resolvidas antes de AWS.

### P2-02 — fundação de rede e cluster

Implementar #71/#72/#74: rede, cluster, IAM/OIDC e node groups. Planejar capacidade e saídas para dependências. Completar #77 com RBAC, quotas e políticas de rede coerentes com banco, DNS, ingress e coleta de telemetria.

**Aceite:** Terraform fmt/validate e plano revisados; cluster/nodes saudáveis; testes de acessos permitidos e negados; inventário de versões, custos e procedimento de atualização documentados.

### P2-03 — banco, credenciais e segredos

Implementar #73/#75/#76/#80/#81: RDS privado, criptografia, backups/retenção, parâmetros, acesso gerenciado a secrets e usuários distintos. Provar leitura restrita para Lambda e permissões de operação/migration separadas do runtime conforme necessidade.

**Aceite:** aplicação e Lambda conectam com TLS; componentes não autorizados não conectam; grants conferidos; backup e restauração testados de forma controlada; outputs não contêm valores secretos.

### P2-04 — KMS, Lambda e Gateway de cliente

Fornecer chave e segredo compatíveis com o módulo existente. Configurar rede, IAM, memória/timeout/concorrência, permissão de invocação e rotas de token/JWKS/customer. Alinhar `iss`, `aud`, `kid`, TTL e URL JWKS com a Pessoa 1.

**Aceite:** fluxo ativo funciona via HTTPS; inexistente/inativo mantêm resposta uniforme; limites geram 429; tokens inválidos são rejeitados; login administrativo continua funcional. A rotação multichave é implementada pela Pessoa 1 e suportada pela configuração de plataforma.

### P2-05 — workloads, migrations e publicação de eventos

Integrar #79/#82/#84/#85: ALB interno e VPC Link privado, secrets/configs, TLS do cliente PostgreSQL, Job de migrations e implantação ordenada. A entrada pública usa o hostname HTTPS padrão do API Gateway; não depende de Ingress público, DNS ou certificado customizado. Injetar JWT/JWKS/EventBridge no runtime; Compose já contém essas configurações, mas os manifests locais auditados ainda não.

Provisionar bus/regra/target e permissões mínimas. Definir retry, DLQ e retenção com a Pessoa 3. Entregar destino do produtor e destino do consumidor por contrato, sem tornar o produtor responsável pela infraestrutura.

**Aceite:** falha de migration impede novo rollout; readiness/liveness funcionam; evento v1 chega ao consumidor e permite correlação; falha de publicação não substitui a exceção original da aplicação.

### P2-06 — completar CI/CD dos quatro repos

Concluir #89/#90/#86: dependências reproduzíveis, lint/testes/segurança, build, validação Terraform, plano revisável, artefatos versionados e deploy. Completar auditoria de dependências da Lambda. Publicar o pacote Lambda de forma persistente e compatível com Linux/runtime.

Configurar GitHub Environments e roles OIDC limitadas por repo/branch, região e cluster de staging. Usar digest no Deployment e versão identificável da Lambda. Habilitar staging após pré-requisitos e testar rollback automatizado sem desfazer migrations destrutivamente; não criar etapa de promoção para produção.

**Aceite:** job de deploy efetivamente executado, smoke aprovado, digest/versão registrados e falha controlada aciona reversão comprovada. Templates e jobs skipped não atendem ao aceite.

### P2-07 — calibrar, homologar e entregar operação

Executar #78/#87 com perfil representativo: CPU, memória, latência, erro, requests/limits, limites de réplicas e janelas de escala documentados. O smoke Kind e o fechamento de #105 não substituem essa medição.

Liberar o staging para Pessoa 1 executar #68 e Pessoa 3 validar APM/alertas/notificações. Registrar teardown e recuperação do staging; concluir acesso do avaliador e revisão dos READMEs. Produção será avaliada em decisão futura, fora desta fase.

**Aceite:** único staging reproduzível, escala para cima/baixo justificada, evidências do fluxo integrado e rollback/recuperação disponíveis; nenhum ambiente AWS de produção é exigido nem inferido da existência de workflow.

## 8. Contratos mínimos de saída e configuração

| Contrato | Conteúdo necessário | Consumidor |
| --- | --- | --- |
| Banco | Endpoint/porta/nome, referências de secrets, SG/rede e requisitos TLS; sem senha em output. | App, Lambda, migration e documentação. |
| Cluster | Nome/região, namespace, identidade de deploy/workload e pontos de entrada/coleta. | CI/CD e Pessoa 3. |
| Autenticação | Issuer, audience, kid, TTL, URL JWKS, referências KMS/secret e rota pública. | Emissor/validador da Pessoa 1. |
| Eventos | Nome/identificador do bus, tipo/source/version, regra/target, DLQ/retry e permissões. | Produtor e consumidor. |
| Release | Commit, imagem por digest, pacote/versão Lambda, migration e evidência de deploy. | Homologação, rollback e pacote final. |
| Operação | URLs/healthchecks, retenção, regiões, filtros e permissões de coleta restritas. | Observabilidade e documentação. |

Na aplicação, mapear `CUSTOMER_JWT_*` e `SERVICE_ORDER_EVENT_BUS_NAME` conforme as configurações existentes. Na Lambda, alinhar `JWT_ISSUER`, `JWT_AUDIENCE`, `JWT_KID`, `JWT_TTL_SECONDS`, `JWT_KMS_KEY_ID` e `DATABASE_SECRET_ARN`. Nomes finais e mecanismos de injeção devem ser conferidos no código da release.

## 9. Verificação e evidências de aceite

| Verificação | Resultado exigido |
| --- | --- |
| Terraform de cada root | `terraform fmt -check -recursive` e `terraform validate` aprovados; plano revisado, sem destruição inesperada ou segredo exposto. |
| Aplicação | `poetry run pytest --cov=src --cov-report=term-missing --cov-fail-under=80`, Bandit e pip-audit aprovados. |
| Lambda | `python -m ruff check .`, `python -m ruff format --check .` e `python -m pytest --cov=lambda_auth --cov-fail-under=80` aprovados. |
| Kubernetes | Probes, rollout, migration anterior ao app, políticas de acesso, HPA e smoke comprovados no ambiente alvo. |
| Gateway | HTTPS/CORS/rotas, Bearer/correlação, 429, erro seguro e regressão administrativa comprovados. |
| Deploy | Quatro pipelines executáveis; staging implantado; imagem por digest e versão Lambda identificadas. |
| Recuperação | Falha controlada, rollback automatizado e teardown/restauração do staging documentados com resultado observável. |

Registrar data/hora, ambiente, commits, revisão da migration, configuração não sensível, links dos runs e resultados. Evidências não devem conter CPF, JWT completo, cookies, senhas, chaves ou strings de conexão. Validar o processo em staging antes de promoção.

## 10. Handoffs e riscos

Regras de operação que devem constar nos READMEs dos roots:

- Identificar explicitamente conta, região, workspace/backend e ambiente antes de revisar o plano.
- Definir retenção de banco/backups compatível com o uso efêmero e com custo por sessão; criar snapshot final somente se aprovado e necessário.
- Separar identidades de runtime, migration, deploy e acesso humano; limitar IAM aos destinos necessários.
- Registrar teardown e custos remanescentes, inclusive recursos compartilhados e armazenamento retido.

À Pessoa 1, entregar URLs, JWKS, configuração JWT, acesso de banco, referência de eventos, commits implantados e mecanismo controlado para teste de falha. Receber contratos funcionais e resultado de #68.

À Pessoa 3, entregar endpoints, inventário, identidades/permissões de coleta, destinos de eventos, DLQ, retenção e evidências de deploy/recuperação. Receber requisitos de instrumentação/consumidor e validação dos painéis/alertas.

| Risco | Mitigação e condição de interrupção |
| --- | --- |
| Custo ou conta/topologia não acordados | Não ativar até registrar recursos, estimativa completa, orçamento, responsável e desligamento. |
| Dois states controlarem a mesma rede/recurso | Resolver ownership antes de aplicar; não corrigir por import improvisado sem plano revisado. |
| Migration incompatível com rollback | Revisar compatibilidade; não automatizar downgrade destrutivo como resposta ao rollout. |
| Secret no Git, log, plano ou state acessível | Restringir acesso e sanitizar evidências; tratar exposição e rotação pelo processo da equipe. |
| Bloqueio da API por JWKS/rede/configuração | Testar conectividade, cache e contrato com o emissor antes da promoção. |
| Perda best-effort de evento | Alertar falha de publicação; não prometer garantia de entrega que o contrato não oferece. |

## 11. Checklist de conclusão

- [x] Base de workloads, Gateway administrativo, CI e build/push identificada e reutilizável.
- [ ] Quatro repos com IaC/código, README, checks, proteção e acesso de avaliação.
- [ ] VPC/EKS/node groups e RDS privados provisionados e documentados.
- [ ] Estado remoto protegido, isolado por ambiente e sem ownership duplicado.
- [ ] Credenciais separadas, Lambda somente leitura, KMS/secrets e IRSA validados.
- [ ] Rotas CPF/JWKS/customer integradas com TLS, correlação e throttling/429.
- [ ] Runtime Kubernetes configurado e migrations bloqueando rollout em falha.
- [ ] EventBridge, targets, IAM, retry/DLQ e consumidor integrados.
- [ ] CD dos quatro repos, digest/versão, smoke e rollback automatizado comprovados.
- [ ] HPA calibrado com carga representativa; #87 e dependências de #68 liberadas.
- [ ] Promoção e recuperação documentadas; evidências fornecidas à Pessoa 3.

**Conclusão da frente:** só encerrar a Pessoa 2 quando a plataforma puder ser reproduzida e demonstrada, com deploy real e recuperação comprovada. Arquivos Terraform, templates de pipeline e execuções que pulam deploy são preparação, não aceite operacional.
