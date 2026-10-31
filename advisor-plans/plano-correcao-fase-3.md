# Plano de correção — Fase 3 (achados A1–A17)

**Data:** 2026-10-27 · **Entrega:** 2026-11-01 · **Executor:** Gustavo
**Base:** [revisão de arquitetura](revisao-arquitetura-fase-3.html), [ADR-0071](../docs/architecture/decisions/ADR-0071-infraestrutura-cloud-fase-3.md), PDF 13SOAT Fase 3.
**Estado:** decisões de escopo atualizadas em 2026-10-27. A implementação e a execução AWS continuam sujeitas às salvaguardas do ADR-0064.

> A conta está no plano Paid e recebeu US$ 140 em créditos; o saldo remanescente ainda precisa ser confirmado. As quotas foram aprovadas em 16 vCPUs On-Demand e 32 Spot. CloudFront/S3 do Angular, domínio próprio e WAF permanecem no escopo. Esta atualização substitui as premissas Free e a antiga linha de corte de 28/10.

## 1. Decisões fechadas nesta rodada

| ID | Decisão | Efeito |
|---|---|---|
| D1 | Sessões AWS efêmeras após confirmação de custo e autorização explícita de apply | Conta Paid com US$ 140 em créditos concedidos; saldo atual precisa ser confirmado. Budgets são alertas e não bloqueiam cobrança. |
| D2 | Homologação e produção no mesmo cluster/RDS (escolha delegada) | Namespaces `auto-shop-hml` e `auto-shop-prd`, databases `autoshop_hml` e `autoshop_prd`, stages `hml` e `prd` no API Gateway. `develop` → hml, `main` → prd. |
| D3 | Endpoint EKS público + privado, autenticação IAM | Sem runner CodeBuild. Role OIDC por repo/branch com access entry restrita aos namespaces. |
| D4 | 3 identidades de banco | `owner` (master gerenciado RDS: bootstrap + migrations), `app_runtime` (DML), `lambda_auth` (SELECT por coluna). |
| D5 | Manter WAF + 429, domínio `api.`, domínio do Angular e CloudFront/S3 no escopo | TLS VPC Link→ALB e Cluster Autoscaler continuam como trabalho futuro. Esta decisão foi confirmada em 2026-10-27 e não será reaberta neste corte. |
| D6 | New Relic free | APM Python, Kubernetes integration, Lambda layer, alertas, dashboards. US$ 0. |

Defaults adotados sem pergunta (podem ser revertidos): manter Lambdas HS256 administrativas (A15) por falta de tempo; NAT Gateway gerenciado único (NAT instance economiza ~US$ 0,20/sessão, não compensa o tempo); Redis e MailHog no cluster; EventBridge → SNS e-mail + SQS DLQ sem Lambda extra.

## 2. Restrições da conta (estado confirmado em 2026-10-27)

| Item | Valor | Impacto |
|---|---|---|
| Conta / plano | `035611741563`, Paid | Não há VPC, EKS, NAT ou RDS ativos; `STAGING_ACTIVE=false`. Permanecem 8 roles IAM. |
| Crédito | US$ 140 concedidos; saldo atual não confirmado | Cost Explorer em US$ 0 pode estar atrasado. Consultar o console antes de cada sessão. |
| Quota vCPU On-Demand | **16** | Aprovada. Revalidar classe e custo no plan da sessão. |
| Quota vCPU Spot | **32** | Aprovada. O sizing escolhido continua sujeito a disponibilidade e custo no plan. |
| Budgets | US$ 1/5/10, apenas alertas | Não bloqueiam cobrança; o gatilho de US$ 20 não está configurado. |

Os limites de 5 vCPUs, o plano Free e os US$ 120 da versão de 2026-10-25 são históricos e não descrevem a conta atual.

## 3. Custo — estimativa anterior, não usar como custo aprovado

As estimativas abaixo vieram do corte inicial e não incluem o escopo público mantido nesta revisão: CloudFront/S3 do Angular, domínio, ACM e o WAF associado ao CloudFront, além do WAF regional da API. Não representam o custo atual nem permitem calcular sessões restantes, pois o saldo de crédito não foi confirmado. Recalcular antes de qualquer apply, mantendo esses componentes no escopo.

Preços: EKS US$ 0,10/h · t3.medium US$ 0,0416/h on-demand, spot médio t3/t3a.medium US$ 0,0163/h (0,0138–0,0206) · NAT US$ 0,045/h + US$ 0,045/GB · IPv4 US$ 0,005/h · ALB US$ 0,0225/h + LCU US$ 0,008 · RDS db.t4g.micro US$ 0,016/h, gp3 US$ 0,115/GB-mês · EBS gp3 US$ 0,08/GB-mês · WAF ACL US$ 5/mês + US$ 1/regra (rateado por hora) · Secrets US$ 0,40/mês · KMS US$ 1/chave-mês · Logs US$ 0,50/GB · API GW REST US$ 3,50/M.

| Cenário por sessão (5 h faturadas) | US$ | Sessões no crédito |
|---|---|---|
| A — ADR-0071 (on-demand, CodeBuild, logs audit, 4 secrets) | 2,04 | 58 |
| **B — Proposta (spot, sem CodeBuild, logs api/auth, 3 secrets, WAF)** | **1,39** | **86** |
| C — Mínimo sem WAF | 1,34 | 89 |

- Custo marginal por hora ligada: **~US$ 0,25**. EKS (36%) e NAT (24%) dominam; WAF é só 3%, por isso foi mantido.
- Os valores por sessão, o total de US$ 9,16 e as sessões estimadas no crédito são históricos; não usar como previsão enquanto o escopo público e o saldo não forem incluídos.
- O risco de recursos esquecidos continua mitigado por `session-down`, cron de destroy e conferência manual de órfãos. Budgets são alertas, não teto de gasto.

## 4. Mapa achado → ação

| Achado | Ação | Fase |
|---|---|---|
| A1 calendário vs Free | D1; atualizar ADR-0071 | 0 |
| A2 hml + prd | D2: namespaces/databases/stages | 3 |
| A3 limite de 17 pods | `ENABLE_PREFIX_DELEGATION=true` no VPC CNI com `max_pods=40` fixo (kube-reserved cresce 11 Mi por pod; 110 pods consumiria ~1,5 GiB por node), sizing de 2 nodes a revalidar com carga e custo. A antiga restrição de 5 vCPU foi removida: as quotas atuais são 16 On-Demand e 32 Spot | 1 |
| A4 ALB fora do state | ALB interno, listener e 2 target groups (hml/prd) no Terraform do `k8s-infra`; `TargetGroupBinding` no app | 1, 3 |
| A5 notificação serverless sem dono | Nova issue; EventBridge rule → SNS e-mail + SQS DLQ em `infra/aws` | 3 |
| A6 EKS privado + CodeBuild | D3 | 1 |
| A7 issues divergentes | Reescrever corpo/critérios das issues afetadas | 0 |
| A8 Swagger privado | `openapi.json` gerado no CI + coleção Postman versionados; link no README | 6 |
| A9 observabilidade | D6 + custom event `ServiceOrderStatusChanged` por transição | 4 |
| A10 identidades | D4 | 2 |
| A11 TLS VPC Link→ALB | Cortado; HTTP no VPC Link, HTTPS público no Gateway | — |
| A12 cookie cross-site | Domínio `api.` + `app.` mesmo site; CORS só `app.` | 4 |
| A13 HPA vs CA | Sem CA; HPA 1–4 réplicas por namespace, demonstrado com carga | 5 |
| A14 logs EKS | Só `api` e `authenticator`, retenção 1 dia | 1 |
| A15 Lambdas HS256 | Mantidas; registrar como débito | — |
| A16 `sslmode=require` | `verify-full` + bundle RDS CA no zip da Lambda e na imagem | 2 |
| A17 budget unblended | Documentar; ajuste de gatilho (seção 3) | 0 |

## 5. Arquitetura alvo (resumo)

```
Cliente ── api.oficina-workshop.com.br ── API Gateway REST (stages hml|prd, WAF, throttle)
                                            ├─ POST /auth/customer/token, GET /.well-known/jwks.json → Lambda lambda-auth (hml|prd)
                                            └─ demais rotas → VPC Link V2 (HTTP) → ALB interno (TF) → TG hml|prd
Operador ── app.oficina-workshop.com.br ── CloudFront + S3 OAC (Angular; build por ambiente: app. = prd, app-hml. = hml)
VPC 10.80.0.0/20 · 2 AZs · 1 NAT
  EKS (público+privado, IAM) · MNG On-Demand 2× t3.medium · prefix delegation
    ns auto-shop-hml / auto-shop-prd: FastAPI (HPA 1–4), Redis, MailHog, TargetGroupBinding, ExternalSecret
    kube-system: LB Controller, ESO, metrics-server, New Relic bundle
  RDS PG16 db.t4g.micro Single-AZ, force_ssl, DBs autoshop_hml/autoshop_prd, 3 identidades por DB
EventBridge bus → rule ServiceOrderProcessingFailed → SNS e-mail (+ SQS DLQ)
SSM /auto-shop/<env>/... contratos · S3 tfstate use_lockfile · KMS RSA por sessão/ambiente
```

Lambda: duas funções (`lambda-auth-hml`, `lambda-auth-prd`) do mesmo artefato, cada uma com `DATABASE_SECRET_ARN` e `JWT_KID` próprios. Issuer/audience por stage: `https://api.oficina-workshop.com.br/hml` e `/prd`.

## 6. Fases e cronograma

Cada fase termina com `terraform fmt/validate`, testes do repo e destroy da sessão. As datas de fase abaixo são referências do cronograma inicial. Em 2026-10-27 foi confirmado que CloudFront/Angular, domínio e WAF continuam no escopo; não há corte automático em 28/10. Qualquer alteração futura exige decisão explícita.

### Fase 0 — Domingo 25/10: decisões e higiene (sem custo)
1. ADR-0071: registrar D1–D6, quotas, custo B, gatilho de pausa, ALB no Terraform, hml/prd, cortes. Atualizar plano Pessoa 2 §6.
2. Reescrever critérios das issues divergentes (A7): `database-infra#1,#3,#4,#5`, `k8s-infra#3,#5,#6,#7`, `auto-shop-system#87,#89,#90,#113`. Fechar `database-infra#6` e `k8s-infra#4` como "fora do escopo" ou rebaixar.
3. Mover `k8s-infra#10` e `#11` para `auto-shop-system`.
4. Criar issues novas: EventBridge→SNS/DLQ; workflows session-up/down + cron; OpenAPI/Postman; RFCs.
5. Pedir aumento de vCPU (não bloqueante).
6. Criar bucket de state (S3 versionado, SSE-S3, TLS-only, Block Public Access). Custo de centavos.
**Aceite:** ADR e issues coerentes; bucket existe.

### Fase 1 — Segunda 26/10: `k8s-infra` (issues 1, 2, 3, 5, 7-ALB, 9)
1. Bootstrap: `envs/staging/`, versões pinadas, backend S3 `use_lockfile=true`, CI (`fmt`, `validate`, `tflint`, `checkov`, `plan` comentado sem valores sensíveis), README, branch protection.
2. Módulo `network`: VPC/subnets do ADR, 1 NAT, gateway endpoint S3, tags de subnet, SGs de node e Lambda.
3. Módulo `eks`: cluster 1.37 público+privado, access entries (humano + role OIDC deploy por repo), add-ons pinados, VPC CNI com `ENABLE_PREFIX_DELEGATION` e NetworkPolicy, logs `api`/`authenticator` retenção 1 dia, MNG On-Demand `t3.medium` min 2 max 2. Spot falhou para o sizing testado na Sessão 1.
4. Módulo `alb`: ALB interno, listener HTTP 80, target groups `hml`/`prd` (target type `ip`), SG permitindo só o VPC Link.
5. Helm: LB Controller (só para TargetGroupBinding), ESO, metrics-server. Namespaces hml/prd com quota, LimitRange, PSS `restricted`, default-deny + regras DNS/ALB/RDS/egress 443.
6. SSM: publicar contratos `/auto-shop/staging/...` (prefixo do ambiente AWS, não do namespace).
7. Workflow `apply` em merge com gate `STAGING_ACTIVE`; `destroy` manual.
**Sessão 1 (~3 h):** apply, `kubectl get nodes`, teste de pods permitidos/negados, destroy.
**Aceite:** cluster Ready, 2 nodes, >17 pods agendáveis por node, SSM publicado, destroy sem órfãos.

### Fase 2 — Terça 27/10: `database-infra` + `lambda-auth` (database-infra 1–5, #85, lambda-auth#3)
1. Bootstrap igual ao `k8s-infra`.
2. Subnet group isolado, SG RDS (5432 só de SG node e SG Lambda), parameter group `rds.force_ssl=1`, RDS PG16 db.t4g.micro gp3 20 GiB, criptografado, backup 1 dia, `skip_final_snapshot=true`, `deletion_protection=false`, master gerenciado no Secrets Manager.
3. Secrets vazios `app_runtime` e `lambda_auth` por ambiente; Job efêmero (Kubernetes, imagem psql, roda no namespace `kube-system` com SA dedicada) cria databases `autoshop_hml`/`autoshop_prd`, usuários e grants, grava `DATABASE_URL` nos secrets. Idempotente.
4. SSM: host, porta, nomes, SG, ARNs dos secrets.
5. `lambda-auth`: `sslmode=verify-full` + bundle CA no pacote (A16), mergear PR #11, workflow de deploy (build zip, upload S3 de artefatos, `terraform apply` do módulo com duas funções), branch protection.
**Sessão 2 (~4 h):** k8s-infra + database-infra + lambda; invocar Lambda direto com cliente sintético; provar `lambda_auth` sem permissão de escrita; destroy.
**Aceite:** Lambda emite JWT com TLS verificado; grants conferidos; secrets sem valores no state.

### Fase 3 — Quarta 28/10: aplicação e Gateway (#84, #86, #85, #113, nova issue EventBridge)
1. `k8s/overlays/hml` e `prd` (Kustomize): imagem por digest, ExternalSecret do `app_runtime`, `TargetGroupBinding`, Redis e MailHog efêmeros, ConfigMap com `CUSTOMER_JWT_*`, `SERVICE_ORDER_EVENT_BUS_NAME`, CORS, exceção de MailHog só em staging (código + teste).
2. CD: `develop` → hml, `main` → prd. Migration Job com credencial `owner` antes do rollout; falha interrompe; smoke `/health/ready`; registro do digest; rollback = reaplicar digest anterior (testado com imagem quebrada proposital).
3. Aposentar `infra/` Terraform-Kubernetes do caminho cloud (README de local apenas).
4. `infra/aws`: VPC Link V2 → listener; stages `hml`/`prd` com variável de estágio para target group/host; rotas cliente → Lambda por stage; WAF com managed common + rate 100/5 min em `POST /auth/customer/token` com 429; throttle 50/100; EventBridge bus + rule + SNS + SQS DLQ + IAM `events:PutEvents` para a role de workload (IRSA).
**Sessão 3 (~5 h):** fluxo cliente ponta a ponta nos dois stages, admin login, 429 demonstrado, evento chega no e-mail; destroy.
**Aceite:** caminho Gateway → VPC Link → ALB → Pod → RDS e Gateway → Lambda funcionando em hml e prd.

### Fase 4 — Quinta 29/10: domínio, Angular, observabilidade, automação de sessão (#92, #93)
1. ACM SAN `api.`, `app.`, `app-hml.`; CNAMEs de validação e destino no Registro.br; custom domain do Gateway com base paths `hml`/`prd`.
2. Angular: bucket S3 privado + CloudFront OAC por ambiente (ou uma distribuição com dois aliases e prefixos); job de publicação com OIDC + invalidação.
3. New Relic: agente Python (APM, logs in context JSON), Kubernetes integration via Helm (nodes/pods/HPA), Lambda layer + integração CloudWatch Metric Streams opcional (custo; preferir layer), synthetic ping no `/health/ready`.
4. Logs JSON com `correlation_id` propagado do Gateway (`X-Correlation-ID` mapeado de `$context.requestId`).
5. Custom event `ServiceOrderStatusChanged {os_id, from, to, duration_s}` em cada transição; métrica `service_order_processing_failed`.
6. Workflows `session-up` (ordem k8s → db → lambda → app hml/prd → gateway → frontend; seta `STAGING_ACTIVE=true`) e `session-down` (ordem inversa; `false`) + **cron 02:00 UTC** chamando `session-down` se ativo.
**Sessão 4 (~5 h):** session-up via workflow, dados no NR, session-down via workflow.
**Aceite:** ambiente sobe e desce só por pipeline; telemetria visível.

### Fase 5 — Sexta 30/10: dashboards, carga, homologação (#94, #78, #87, #68, #91)
1. Dashboards NR: latência p50/p95/p99 por rota, erro 4xx/5xx, CPU/mem por pod, réplicas HPA, uptime, volume diário de OS, tempo médio por status, falhas de integração (Invertexto, BrasilAPI, EventBridge).
2. Alertas: p95 > 2 s 5 min, synthetic falha, `service_order_processing_failed` > 0 → e-mail; runbook linkado.
3. Carga com `k6` ou `hey` contra hml: HPA 1→4 e volta; registrar requests/limits calibrados.
4. #68: roteiro de homologação (ativo, inativo, token inválido/expirado/aud errada, OS de outro cliente, evento).
5. Branch protection equivalente nos 4 repos (`enforce_admins=true`, checks reais); `soat-architecture` em todos.
**Sessão 5 (~5 h):** carga + homologação + evidências sanitizadas.

### Fase 6 — Sábado 31/10: vídeo e documentação
1. **Sessão 6 (~4 h):** gravar vídeo (≤15 min): PR → CI → merge → deploy automático hml e prd, CPF → JWT, API protegida, 429, dashboard ao vivo, logs/traces, alerta de falha de OS. Destroy ao final.
2. READMEs dos 4 repos (propósito, stack, execução/deploy, diagrama do repo, links Swagger/Postman, custo, teardown).
3. RFCs em `docs/rfc/`: escolha de nuvem, banco, autenticação. ADRs novos: HPA, padrão de comunicação (síncrono + evento de falha). Justificativa do banco + ER.
4. `openapi.json` + coleção Postman versionados.

### Fase 7 — Domingo 01/11: entrega
PDF único (links dos repos, vídeo, docs, confirmação `soat-architecture`). Sessão reserva só se algo falhar. Exportar state criptografado antes de 06/11.

## 7. Riscos

| Risco | Prob. | Mitigação |
|---|---|---|
| Prazo curto para a Fase 3 | Alta | Manter as entregas confirmadas; acompanhar dependências e riscos sem corte automático de CloudFront/domínio/WAF. |
| Custo após esgotar os créditos | Média | Conta Paid, US$ 140 em créditos concedidos; saldo não confirmado. Budgets de US$ 1/5/10 só alertam. Recalcular custo incluindo CloudFront, WAF, domínio e teardown antes da sessão. |
| Compatibilidade de instância | Média | Quotas aprovadas: 16 vCPUs On-Demand e 32 Spot. A Sessão 1 usou On-Demand após Spot falhar no sizing selecionado; revalidar tipo e preço no plan. |
| Recurso esquecido ligado | Média | Cron de destroy + budget alerts + checklist de teardown. |
| ENIs da Lambda atrasam destroy da VPC | Média | Destroy da Lambda antes da rede; timeout ampliado no Terraform. |
| Validação ACM no Registro.br demorar | Média | Pedir certificado na Sessão 2 (não depende do resto). |
| Budget interpretado como bloqueio | Média | Os budgets existentes são alertas e não impõem teto de gasto; o gatilho de US$ 20 não está configurado. |

## 8. Fora do escopo (documentar como trabalho futuro)

TLS VPC Link → ALB; Cluster Autoscaler/Karpenter; endpoint EKS privado + CodeBuild; 4ª identidade de banco; RDS Proxy; Multi-AZ; produção em conta/cluster separado; remoção das Lambdas HS256.

## 9. Decisões registradas em 2026-10-27 e gates restantes

As decisões de escopo abaixo foram confirmadas pelo titular e orientam a implementação documental e de código. Elas não autorizam provisionamento nem `terraform apply`.

| Tema | Estado vigente |
|---|---|
| Conta e créditos | Conta Paid; US$ 140 em créditos concedidos; saldo atual desconhecido. Cost Explorer mostrou US$ 0, sujeito a atraso. |
| Limites e alertas | Quotas aprovadas: 16 vCPUs On-Demand e 32 Spot. Budgets de US$ 1/5/10 são alertas; não há gatilho de pausa de US$ 20 configurado. |
| Topologia de ambientes | Uma infraestrutura AWS efêmera atende aos namespaces lógicos `hml` e `prd`; sem conta, cluster ou RDS de produção separado nesta fase. |
| Acesso ao EKS | Endpoint público e privado com IAM access entries e OIDC restrito. Não usar CodeBuild. |
| Banco | Três identidades por database: `owner`, `app_runtime` e `lambda_auth`. O bootstrap escolhido usa init containers `aws-cli` e `postgres:16`, publica com `PutSecretValue` e mantém arquivos e valores em `tmpfs`. |
| Entrada pública | CloudFront/S3 para o Angular, domínio próprio, ACM e WAF permanecem no escopo, conforme decisão expressa em 2026-10-27. O WAF do CloudFront usa escopo `CLOUDFRONT`; o WAF do API Gateway permanece `REGIONAL`. |
| Próximos gates | Recalcular o custo com todo o escopo público, confirmar saldo e capacidade de teardown, concluir o resolver seguro de secrets exigido pelo projeto, revisar os plans e obter autorização específica antes de qualquer apply. |

O plano está aprovado para implementação. Ainda dependem de trabalho: mudanças externas no GitHub, conclusão do bootstrap seguro e autorização operacional específica para provisionar AWS. Nenhum budget existente limita ou interrompe gasto.
