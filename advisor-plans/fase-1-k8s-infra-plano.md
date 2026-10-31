# Fase 1 — Plano de implementação do `k8s-infra`

**Data:** 2026-10-25 · **Atualizado:** 2026-10-26 · **Janela:** 25–26/10 · **Clone:** `C:\Users\gusta\Documents\Codes\pos\k8s-infra`
**Base:** ADR-0071 (revisão 2026-10-25), `plano-correcao-fase-3.md`, issues `k8s-infra#1–#9`.
**Estado:** implementação e validação real concluídas. PRs #13 e #14 foram mergeados na `main`; CI, apply, smoke test, destroy e checagem de órfãos passaram. A infraestrutura de staging foi removida após a validação.

O apply inicial revelou que o plano Free rejeitava `t3.medium`/`t3a.medium`. O PR #14 alterou o node group para On-Demand, mantendo o endereço Terraform do recurso. Com autorização do titular, a conta foi atualizada para Paid em 2026-10-26 via API AWS; a leitura confirmou US$ 140 em créditos concedidos. O saldo atual não foi confirmado nesta revisão.

## 1. Requisitos reafirmados

> **Estado atual — 2026-10-27:** a conta permanece Paid; os US$ 140 foram concedidos como créditos, mas o saldo remanescente não foi confirmado. As quotas aprovadas são 16 vCPUs On-Demand e 32 Spot. A Sessão 1 usou On-Demand após falha de Spot para o sizing testado. Este registro de execução não substitui a atualização vigente do ADR-0071.

Entregar, em Terraform reproduzível, a plataforma de cluster do único ambiente AWS (`staging`), que hospeda os namespaces `auto-shop-hml` e `auto-shop-prd`:

- VPC dedicada `10.80.0.0/20` em 2 AZs, 1 NAT, subnets públicas, de workload e isoladas (RDS).
- EKS 1.37 com endpoint público + privado, autenticação IAM (access entries), sem CodeBuild.
- Managed Node Group On-Demand 2× `t3.medium`, prefix delegation, `max_pods=40`.
- ALB interno com target groups hml/prd criados no Terraform (registro de Pods por `TargetGroupBinding`).
- Namespaces com quota, LimitRange, Pod Security `restricted`, RBAC e NetworkPolicy default-deny.
- Add-ons: AWS Load Balancer Controller, External Secrets Operator, metrics-server.
- Contratos publicados no SSM; CI com `fmt`/`validate`/`tflint`/`checkov`/`terraform test`/`plan`; apply só com `STAGING_ACTIVE=true`.

## 2. Fatos verificados agora (somente leitura)

| Item | Valor |
|---|---|
| EKS 1.37 em `us-east-1` | disponível; add-ons: vpc-cni `v1.23.2-eksbuild.8`, coredns `v1.14.7-eksbuild.22`, kube-proxy `v1.37.0-eksbuild.32`, pod-identity-agent `v1.4.1-eksbuild.2`, metrics-server `v0.9.0-eksbuild.14` |
| AZs escolhidas | `use1-az1` (us-east-1a) e `use1-az2` (us-east-1b); ambas oferecem t3/t3a.medium; `use1-az3` excluída |
| Local | Terraform 1.15.8, kubectl 1.34; **sem** helm, tflint, checkov (rodam no CI; instalação local opcional) |
| Convenção irmã (`lambda-auth`) | AWS provider `~> 6.0`, `allowed_account_ids`, `default_tags` |

## 3. Decisões de implementação (dentro do ADR)

| Tema | Escolha | Motivo |
|---|---|---|
| Módulos | `terraform-aws-modules/vpc` e `terraform-aws-modules/eks` com versões fixadas | Economiza 1–2 dias; padrão de mercado; compatível com provider 6 (validar no `init`) |
| Identidade de Pods | **EKS Pod Identity** em vez de IRSA | Sem trust policy por ServiceAccount; LB Controller e ESO suportam. O provedor OIDC do cluster segue criado (contrato do ADR), mas não é usado nesta fase |
| Separação de state | 3 stacks: `bootstrap` (persistente), `foundation` (rede, EKS, ALB, SSM), `platform` (Helm, namespaces, políticas) | Evita o problema de providers Kubernetes/Helm dependentes de cluster ainda inexistente; destroy em ordem simples |
| Entrada hml/prd no ALB | Dois listeners: `8001` → TG hml, `8002` → TG prd | O Gateway escolhe o ambiente pela porta da integração; dispensa reescrita de Host |
| Subnets CodeBuild | Faixas `10.80.0.64/27` e `10.80.0.96/27` ficam **não alocadas** | CodeBuild saiu do escopo |
| GitHub OIDC | Provider IAM (singleton da conta) e roles dos 4 repos no stack `bootstrap` | Recursos IAM são gratuitos e persistem entre sessões |
| Primeiro commit | Commit inicial direto na `main` só com README e `.gitignore`, depois branch protection e todo o resto por PR | Repositório vazio não tem `main`; não há outra forma de abrir o primeiro PR |

## 4. Estrutura do repositório

```
k8s-infra/
  README.md  .gitignore  .tflint.hcl  .checkov.yaml  CHANGELOG.md
  modules/
    network/        VPC, subnets, NAT, gateway endpoint S3, SGs de node e Lambda, tags de subnet
    alb/            ALB interno, SG, listeners 8001/8002, target groups ip hml/prd, health /health/ready
    ssm-contract/   publica mapa nome→valor como SSM String/StringList (sem SecureString)
  envs/staging/
    bootstrap/      GitHub OIDC provider; roles plan (ReadOnly+state) e deploy por repo; política do bucket de state
    foundation/     network + eks (registry) + node group + add-ons EKS + alb + ssm-contract
    platform/       helm (LB Controller, ESO), Pod Identity associations, namespaces, quota, LimitRange,
                    PSS labels, RBAC, NetworkPolicies
  tests/            *.tftest.hcl (mock_provider) por módulo
  scripts/
    smoke.sh        kubectl get nodes, contagem de pods, testes de NetworkPolicy permitida/negada
    orphans.sh      lista EKS/NAT/ALB/EIP/ENI/EBS com tag do projeto e falha se sobrar algo
  .github/workflows/
    ci.yml          PR: fmt, validate, tflint, checkov, terraform test, plan (role plan) com resumo sanitizado
    apply.yml       push main: apply foundation→platform se STAGING_ACTIVE=true; workflow_dispatch manual
    destroy.yml     workflow_dispatch: platform→foundation + orphans.sh
```

State: bucket `auto-shop-tfstate-035611741563-use1`, chaves `k8s-infra/staging/{bootstrap,foundation,platform}.tfstate`, `use_lockfile=true`.

## 5. Contrato SSM publicado (`/auto-shop/staging/...`)

| Parâmetro | Origem |
|---|---|
| `network/vpc-id`, `network/vpc-cidr` | foundation |
| `network/workload-private-subnet-ids` (StringList) | foundation |
| `network/rds-isolated-subnet-ids` (StringList) | foundation |
| `network/eks-node-security-group-id`, `network/lambda-security-group-id` | foundation |
| `eks/cluster-name`, `eks/cluster-endpoint`, `eks/oidc-provider-arn` | foundation |
| `gateway/internal-alb-arn`, `gateway/internal-alb-dns`, `gateway/internal-alb-security-group-id` | foundation |
| `gateway/listener-arn/{hml,prd}`, `gateway/target-group-arn/{hml,prd}` | foundation |
| `domain/root`, `domain/api-url`, `domain/frontend-url/{hml,prd}` | foundation (variáveis) |

Convenção de nome de segredos que o `database-infra` deve seguir (para o IAM do ESO por padrão de ARN): `auto-shop/staging/{hml,prd}/app-runtime`.

## 6. Etapas (TDD onde aplicável: teste `terraform test` com `mock_provider` antes do módulo)

| # | Etapa | Issue | Esforço | Aceite |
|---|---|---|---|---|
| 1 | Clonar, commit inicial (README, `.gitignore`), push `main`, branch protection (PR, 1 check, sem force push), `soat-architecture` com read | #1 | 0,5 h | `main` protegida |
| 2 | `bootstrap`: OIDC provider, roles `gh-plan-<repo>` (ReadOnly + state do repo) e `gh-deploy-<repo>` (escopo por serviço, sem `iam:*` fora do path `/auto-shop/`), restritas a `repo:<org>/<repo>:ref:refs/heads/main` e `pull_request`. Apply local (gratuito) | #1 | 2 h | `aws sts assume-role-with-web-identity` a partir do CI funciona |
| 3 | `modules/network` + testes: subnets privadas sem `map_public_ip`, RDS sem rota default, 1 NAT, tags `kubernetes.io/role/internal-elb`, CIDRs do ADR | #2 | 2 h | `terraform test` verde |
| 4 | `foundation`: EKS 1.37 (endpoint público+privado), access entries (Gustavo + roles deploy), logs `api`/`authenticator` retenção 1 dia, MNG On-Demand 2 nodes (`min=max=2`), add-ons pinados, vpc-cni com `ENABLE_PREFIX_DELEGATION=true`, `WARM_PREFIX_TARGET=1`, NetworkPolicy ligada, `max_pods=40` no launch template | #3, #4 | 3 h | `validate` + `plan` limpos |
| 5 | `modules/alb` + testes: internal, 2 listeners, 2 TGs `ip`, SG ALB←VPC CIDR 8001/8002, regra node SG←ALB SG porta da app | #7 | 1,5 h | `terraform test` verde |
| 6 | `modules/ssm-contract` + publicação | #9 | 1 h | nenhum `SecureString`; nomes do quadro 5 |
| 7 | `platform`: Helm LB Controller (Pod Identity, política oficial versionada) e ESO (Pod Identity limitada a `auto-shop/staging/*/app-runtime*`); namespaces hml/prd com PSS restricted, quota, LimitRange; NetworkPolicy default-deny + DNS, ingress da VPC na porta da app, egress RDS 5432 (subnets isoladas), egress 443, intra-namespace (Redis/MailHog); RBAC de leitura de Secrets restrito ao namespace | #5, #8 | 3 h | `validate` + `plan` limpos |
| 8 | CI/CD: `ci.yml`, `apply.yml`, `destroy.yml`, variável `STAGING_ACTIVE`, resumos sem valores sensíveis | #1, #9 | 2 h | PR mostra checks verdes |
| 9 | README (propósito, stack, diagrama Mermaid, execução, contratos, custo por sessão, teardown) e CHANGELOG | #1, #9 | 1 h | revisão |
| 10 | Revisão: code-review + security-review (agentes) e correções | — | 1 h | sem achado crítico |
| 11 | **Sessão 1:** apply foundation→platform, `smoke.sh`, destroy e `orphans.sh` concluídos. Nodes Ready com 40 pods alocáveis cada; add-ons e políticas de rede validados; recursos do staging removidos. | #2–#9 | concluída | CI e validação AWS aprovados; zero órfãos |

Total de implementação: ~17 h de trabalho. Implemento diretamente (já tenho todo o contexto). Revisões por subagentes `code-reviewer` e `security-reviewer`.

## 7. Riscos

| Risco | Mitigação |
|---|---|
| Plano Free bloqueava `t3.medium`/`t3a.medium` | Conta atualizada para Paid após autorização; o caminho On-Demand foi validado em staging. O plano Paid não pode ser revertido para Free; cobranças padrão podem ocorrer após o saldo de créditos. |
| Quotas aprovadas: 16 vCPU On-Demand e 32 Spot | A Sessão 1 usou On-Demand após Spot falhar para o sizing escolhido |
| Versões dos módulos incompatíveis com provider 6 | Fixar versões testadas no `init`; ajustar antes de abrir PR |
| Role de deploy ampla demais | Escopo por serviço + condição de tag/path; registrar o trade-off no README |
| Destroy travado por ENIs | `platform` destruído antes de `foundation`; `orphans.sh` ao final; timeouts ampliados |
| `checkov` acusar regras esperadas (endpoint público, etc.) | Supressões explícitas com justificativa em `.checkov.yaml` |

## 8. Fora desta fase

RDS e identidades de banco (Fase 2), Lambda, Gateway, deploy da aplicação, Redis/MailHog (Fase 3), New Relic (Fase 4), HPA e carga (Fase 5).

## 9. Resultado da validação real

- PR #13 (`4a82e5b`) corrigiu o acesso EKS/IAM; PR #14 (`cc44e3e`) trocou Spot por On-Demand preservando o endereço Terraform. Ambos foram mergeados e o CI passou.
- A conta AWS 035611741563 foi atualizada de Free para Paid com autorização do titular. `GetAccountPlanState` confirmou `ACTIVE`/`PAID`; US$ 140 foram concedidos em créditos. O saldo atual não foi confirmado.
- [Workflow apply e smoke](https://github.com/Software-Architecture-Group-7-FIAP/k8s-infra/actions/runs/40365996327): foundation e platform aplicadas; os dois nodes ficaram Ready com 40 pods alocáveis cada; coredns, metrics-server, AWS Load Balancer Controller, External Secrets e API de métricas passaram. A política permitiu DNS/HTTPS e negou hml→prd e HTTP/80.
- [Workflow destroy e orphans](https://github.com/Software-Architecture-Group-7-FIAP/k8s-infra/actions/runs/40368715372) passou. Checagem independente confirmou EKS, VPC, NAT, EIP, ALB, ENIs, volumes, ASG, instâncias, parâmetros SSM e state lock removidos. Os três states Terraform e o backend S3 foram preservados.
- Estimativa de operação futura: até aproximadamente US$ 0,26/h para a infraestrutura completa e US$ 1,32 por 5 h, incluindo 2 nodes On-Demand `t3.medium`; os custos variam conforme uso e região.
