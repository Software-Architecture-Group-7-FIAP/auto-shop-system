# Fase 2 — Plano de implementação do `database-infra`

**Data do plano:** 2026-10-26 · **Estado revisado:** 2026-10-27 · **Planejado por:** agente Plan (opus, effort medium)
**Estado desta revisão:** o usuário autorizou implementar o bootstrap com init containers `aws-cli` + `postgres:16`, `PutSecretValue` e arquivos/payloads temporários em tmpfs. Isso não autoriza `terraform apply`, deploy, leitura de valores de secrets pelo agente ou mutação AWS; a sessão de aplicação continua sujeita à autorização explícita do ADR-0064.

**Decisões confirmadas em 2026-10-27:** manter a publicação por `PutSecretValue`; manter master, senhas, payloads, `pgpass`, SQL gerado, cache/configuração AWS e saídas temporárias apenas em volume `emptyDir.medium: Memory`; manter o domínio próprio, WAF e CloudFront/S3 do Angular no escopo Fase 3. O caminho de resolução do master deve obedecer à política de secrets do projeto e não retornar valores ao agente.

**Base:** issues `database-infra#1–#5`, [ADR-0071](../docs/architecture/decisions/ADR-0071-infraestrutura-cloud-fase-3.md), `k8s-infra@main` (`cc44e3e`) como implementação de referência.

## Estado inicial verificado

Remoto público `database-infra` **vazio** (size 0, sem branches, default configurado como `main`). Atualização do coordenador nesta revisão: checkout já preparado em `C:\Users\gusta\Documents\Codes\pos\database-infra`, branch local `main` sem commits e sem `origin/main`. Não reclonar nem recriar o repositório. Configuração informada abaixo deve ser reconfirmada por metadados antes da futura publicação:

```
AWS_DEPLOY_ROLE_ARN = arn:aws:iam::035611741563:role/auto-shop/gh-deploy-database-infra
AWS_PLAN_ROLE_ARN   = arn:aws:iam::035611741563:role/auto-shop/gh-plan-database-infra
AWS_REGION          = us-east-1
```

Environment `staging` informado como existente, restrito a `main`, e `soat-architecture` com read; confirmar antes de publicar. Estado informado em 2026-10-27: conta **Paid**, US$ 140 em créditos concedidos (saldo restante não confirmado), quotas aprovadas de 16 vCPUs On-Demand e 32 Spot. Não repetir premissas Free como estado atual. Reconfirmar custos antes da próxima sessão; não executar apply sem autorização explícita.

**Precedência e evidência (2026-10-26):** AGENTS.md e RTK.md lidos; ADR-0071 (revisão de escopo prevalece sobre histórico), `plano-correcao-fase-3.md`, resultado atualizado de `fase-1-k8s-infra-plano.md`, issues #1–#5 lidas pelo conector GitHub e checkout `pos/k8s-infra` conferidos. #1/#3/#4/#5 têm escopo vigente de 2026-10-25; #2 mantém cabeçalho autoritativo de 2026-10-23. As decisões do projeto prevalecem sobre defaults de produção das skills AWS consultadas (`aws-database` → `rds-oss` e `creating-secrets-using-best-practices`, retornada pelo catálogo de Secrets Manager): PG16, Single-AZ, chave gerenciada AWS, backup 1 dia, sem CMK extra/Lambda de rotação/Performance Insights, remoção integral no mesmo dia. `prd` é database lógico do staging efêmero, não root production. Renovar credenciais por sessão não exige desativar a gestão nativa do master RDS.

## 1. Layout do repositório

```
database-infra/
├── .checkov.yaml  .gitattributes  .gitignore  .tflint.hcl  CHANGELOG.md  README.md
├── .github/workflows/{ci,apply,destroy}.yml
├── envs/staging/database/{main,variables,outputs,versions}.tf + .terraform.lock.hcl   # ÚNICO root
├── modules/
│   ├── db-network/   + tests/db-network.tftest.hcl
│   ├── db-instance/  + tests/db-instance.tftest.hcl
│   ├── db-secrets/   + tests/db-secrets.tftest.hcl
│   └── ssm-contract/ # copiado verbatim do k8s-infra, com o teste
├── sql/{00-bootstrap.sql,10-lambda-grants.sql}
└── scripts/{plan-summary.sh,plan-guard.sh,bootstrap-db.sh,smoke.sh,orphans.sh}
```

**Decisões:**
- **Sem stack `bootstrap`.** OIDC provider, roles `gh-*`, boundary `auto-shop-boundary`, políticas de state e o bucket foram criados pelo `envs/staging/bootstrap` do `k8s-infra` (que itera os 4 repos). O `DenyEditingCiIdentities` bloqueia `gh-deploy-database-infra` de tocar nisso de qualquer forma.
- **Sem `envs/production/`** (ADR-0071 rev. 2026-10-25). `hml`/`prd` são dois **databases na mesma instância**.
- **Um único root**, não o split `foundation`/`platform` do `k8s-infra` — aqui não há provider `kubernetes`/`helm` (ver §5), tudo é AWS e compartilha um ciclo de vida, e a issue #1 fixa a chave de state em `database-infra/staging/terraform.tfstate` (singular).
- **Sem módulos do registry.** `aws_db_instance` + subnet group + parameter group são 3 recursos; `terraform-aws-modules/rds` só adiciona superfície. Consequência: **não** copiar `CKV_TF_1` para o `.checkov.yaml`.

`versions.tf` do root:

```hcl
terraform {
  required_version = ">= 1.10.0, < 2.0.0"
  required_providers { aws = { source = "hashicorp/aws", version = "~> 6.70" } }
  backend "s3" {
    bucket = "auto-shop-tfstate-035611741563-use1"
    key    = "database-infra/staging/terraform.tfstate"
    region = "us-east-1"
    encrypt = true
    use_lockfile = true
  }
}
provider "aws" {
  region              = var.aws_region
  allowed_account_ids = [var.expected_account_id]   # "035611741563"
  default_tags { tags = {
    Project = "auto-shop", Environment = "staging",
    ManagedBy = "Terraform", Repository = "database-infra", Stack = "database" } }
}
```

Módulos: mesmo `required_version`/`required_providers`, sem backend e sem bloco `provider`. CI fixa `TF_VERSION: 1.15.8`.

## 2. Passos ordenados (1 PR por passo, CI verde antes do merge)

### Passo 0 — Skeleton (local) — #1
Preparar skeleton no checkout existente; copiar `.gitignore`, `.gitattributes`, `.tflint.hcl` do `k8s-infra` no SHA conferido e criar CHANGELOG próprio, sem atribuir a este repo a história alheia; `modules/ssm-contract/` **verbatim** (com teste e lock); `envs/staging/database/` válido-mas-vazio.
**Gate de publicação:** remoto vazio exige decisão explícita do dono sobre o commit inicial mínimo em `main` (exceção usada na Fase 1, em conflito com a regra geral de nunca commit direto). Preparar tudo localmente, sem publicar até essa decisão; depois proteger `main` antes do código de infraestrutura.
**Aceite:** `fmt -check -recursive`, `init -backend=false`/`validate` do root, `test` do ssm-contract passam. Branch protection em `main` (PR obrigatório, check `ci.yml`, sem force push).

### Passo 1 — `ci.yml` + `plan-guard.sh` (local) — #1, #2
Estrutura idêntica à do `k8s-infra`: triggers `pull_request:[main]` + `workflow_dispatch` + `schedule`; job `environment-policy` (assert política de branch = só `main`); job `static` (fmt, validate por stack, `terraform test` por módulo, tflint v0.65.0, checkov com `.checkov.yaml`, shellcheck); job `plan` (`needs: static`, `id-token: write`).

O job `plan` **sonda o contrato upstream antes de planejar** — o plan lê SSM do `k8s-infra`:

```bash
required=( /auto-shop/staging/network/vpc-id
           /auto-shop/staging/network/rds-isolated-subnet-ids
           /auto-shop/staging/network/eks-node-security-group-id
           /auto-shop/staging/network/lambda-security-group-id
           /auto-shop/staging/eks/cluster-name )
invalid="$(aws ssm get-parameters --names "${required[@]}" --query 'InvalidParameters' --output json)"
if [[ "$invalid" == "[]" ]]; then
  ./scripts/plan-summary.sh envs/staging/database >> "$GITHUB_STEP_SUMMARY"
  ./scripts/plan-guard.sh  envs/staging/database >> "$GITHUB_STEP_SUMMARY"
else
  echo "### database: skipped (contrato SSM do k8s-infra não publicado: $invalid)" >> "$GITHUB_STEP_SUMMARY"
fi
```

Ações de terceiros fixadas pelos mesmos SHAs do `k8s-infra` (`actions/checkout@3d3c42e5…` com `persist-credentials: false`, `hashicorp/setup-terraform@dfe3c3f8…` com `terraform_wrapper: false`, `aws-actions/configure-aws-credentials@e1253824…`).

**O plan não pode ler valores de segredos.** `gh-plan-database-infra` = `ReadOnlyAccess` menos `auto-shop-plan-restrictions`, que **nega** `secretsmanager:GetSecretValue`, leituras DynamoDB e todo `ssm:GetParameter*` fora de `/auto-shop/*` e `aws/service/*`. Logo: **nunca** um `data "aws_secretsmanager_secret_version"`.

`scripts/plan-guard.sh` falha o job se o plan JSON violar invariantes (critério "validar no CI que o plano mantém RDS privado e não abre 5432 para a Internet" da #2). Asserções sobre `terraform show -json`:

| Asserção | Por quê |
|---|---|
| todo `aws_db_instance.after.publicly_accessible == false` | #2, #3 |
| `storage_encrypted == true`, sem CMK explicitamente configurada; ARN computado de `aws/rds` no refresh é permitido | #3 (chave gerenciada AWS) |
| `engine == "postgres"`, `engine_version == "16.15"` | #3 |
| `instance_class == "db.t4g.micro"`, `allocated_storage == 20`, `storage_type == "gp3"` | #3, custo |
| `multi_az == false`, `deletion_protection == false`, `skip_final_snapshot == true`, `delete_automated_backups == true`, `backup_retention_period == 1` | #3, teardown |
| nenhum ingress com `cidr_ipv4 == "0.0.0.0/0"` ou `cidr_ipv6 == "::/0"` | #2 |
| todo ingress tem `referenced_security_group_id` não nulo | #2 (nunca CIDR amplo) |
| nenhum `aws_ssm_parameter` com `type == "SecureString"` | #5 |
| nenhum `aws_ssm_parameter.after.value` casando `postgres(ql)?://` ou `password` | #4, #5 |
| zero recursos `aws_secretsmanager_secret_version` | #4 (nenhuma senha em state) |
| zero recursos `aws_rds_proxy*` | #5, #6 fechada |

Só `jq`; imprimir endereços, nunca valores (mesma disciplina do `plan-summary.sh`). Resumo e guard devem ler o **mesmo plano salvo**, não dois plans independentes. Binário/JSON só em diretório temporário restrito com trap de limpeza, nunca como artifact/comentário. Testes de fixtures inválidas antes do guard: recurso público, inline ingress, ingress/egress por CIDR IPv4/IPv6, protocolo/porta/origem divergentes, Proxy, DSN em outputs/SSM, secret version data/resource e gerador de password. Falhar em unknown crítico, exceto IDs futuros cujo vínculo à origem aprovada seja provado no grafo e confirmado pelo smoke. Não exigir kms_key_id nulo em state após refresh: a AWS pode preencher ARN gerenciado. Plan skipped com upstream desligado é evidência **pendente**, não aceite do plano real; AccessDenied/rede não são ausência de parâmetros.

### Passo 2 — `modules/db-network` (local, TDD) — #2
**Testes primeiro** (`mock_provider "aws" {}`, zero chamadas AWS): subnet group usa só as subnets isoladas; ingress só por `referenced_security_group_id` (sem `cidr_ipv4`, tcp 5432); 1 regra por origem permitida; **zero egress**; rejeita <2 subnets; rejeita mapa de origens vazio. Contar subnets não prova AZs: consultar metadados EC2 e validar duas AZs distintas, mesma VPC, IDs sem repetição e route tables sem default IPv4/IPv6.

**Depois construir:** `aws_db_subnet_group` (`subnet_ids` = isoladas, validação `>= 2`); `aws_security_group "rds"` sem regras inline; `aws_vpc_security_group_ingress_rule` com `for_each` sobre `{ eks-nodes = sg, lambda = sg }`, tcp 5432. **Nenhuma regra de egress** — RDS não inicia conexões, as subnets isoladas não têm rota default, e SG sem egress nega tudo. Outputs: `security_group_id`, `subnet_group_name`.

### Passo 3 — `modules/db-secrets` (local, TDD) — #4
**Testes primeiro:** nomes casam o contrato do ESO; `recovery_window_in_days == 0`; `kms_key_id == null`; o módulo não declara `aws_secretsmanager_secret_version`; rejeita prefixo fora do contrato.

**Depois construir:** somente `aws_secretsmanager_secret` — **nunca** `..._version`. Dois `for_each` sobre `var.environments`: `runtime` → `${prefix}/${env}/app-runtime`; `lambda` → `${prefix}/${env}/lambda-auth`. Ambos `recovery_window_in_days = 0`, sem `kms_key_id`. Validação do `prefix`: `can(regex("^auto-shop/[a-z0-9-]+$", ...))`.

> **O nome `runtime` é contrato rígido.** `k8s-infra/envs/staging/platform/addons.tf` escopa a role do ESO a `secret:auto-shop/staging/${env}/app-runtime-*`. Qualquer outro nome e o External Secrets silenciosamente não lê.

### Passo 4 — `modules/db-instance` (local, TDD) — #3
**Testes primeiro:** postgres 16 / `db.t4g.micro` / Single-AZ / privado; criptografia gerenciada AWS; gp3 20 GiB sem autoscaling; parameter group `postgres16` com `rds.force_ssl=1`; teardown efêmero; RDS gerencia a senha master; sem Performance Insights/enhanced monitoring; rejeita retenção > 1 dia; rejeita `multi_az = true`. Mockar `aws_db_instance` com `address`/`port`/`master_user_secret` determinísticos.

**Depois construir** (argumentos críticos):

```hcl
resource "aws_db_parameter_group" "this" {
  name_prefix = "${var.name}-pg16-"
  family      = "postgres16"
  parameter { name = "rds.force_ssl",              value = "1" }
  parameter { name = "log_min_duration_statement", value = "1000" }
  lifecycle { create_before_destroy = true }
}

resource "aws_db_instance" "this" {
  identifier = var.name                  # auto-shop-staging
  engine = "postgres"
  engine_version = "16.15"               # API DescribeDBEngineVersions em us-east-1: evidência fornecida
  auto_minor_version_upgrade = false
  instance_class = "db.t4g.micro"
  allocated_storage = 20
  storage_type = "gp3"
  max_allocated_storage = 0              # sem autoscaling -> sem surpresa de storage
  storage_encrypted = true               # chave aws/rds; kms_key_id intencionalmente ausente
  db_name = null                         # databases criados pelo Job, não pelo RDS
  username = "autoshop_owner"
  manage_master_user_password = true     # RDS grava rds!db-<id> no Secrets Manager
  db_subnet_group_name = var.db_subnet_group_name
  vpc_security_group_ids = [var.security_group_id]
  publicly_accessible = false
  multi_az = false
  availability_zone = null
  ca_cert_identifier = "rds-ca-rsa2048-g1"   # fixo: clientes verify-full sabem o bundle
  parameter_group_name = aws_db_parameter_group.this.name
  apply_immediately = true
  backup_retention_period = 1
  backup_window = var.backup_window     # UTC, deve ocorrer dentro da sessão/ensaio de restore
  maintenance_window = "sun:07:00-sun:07:30"
  copy_tags_to_snapshot = true
  delete_automated_backups = true        # SEM isso, backups sobrevivem à instância e cobram
  skip_final_snapshot = true
  deletion_protection = false
  performance_insights_enabled = false
  monitoring_interval = 0
  enabled_cloudwatch_logs_exports = []
}
```

Outputs: `address`, `port`, `identifier`, `master_user_secret_arn = ...master_user_secret[0].secret_arn`, `resource_id`.

### Passo 5 — Root: consumir contrato, IAM, publicar SSM — #2, #3, #4, #5

```hcl
data "aws_ssm_parameter" "vpc_id"           { name = "/auto-shop/staging/network/vpc-id" }
data "aws_ssm_parameter" "rds_subnet_ids"   { name = "/auto-shop/staging/network/rds-isolated-subnet-ids" }  # StringList
data "aws_ssm_parameter" "eks_node_sg_id"   { name = "/auto-shop/staging/network/eks-node-security-group-id" }
data "aws_ssm_parameter" "lambda_sg_id"     { name = "/auto-shop/staging/network/lambda-security-group-id" }
data "aws_ssm_parameter" "eks_cluster_name" { name = "/auto-shop/staging/eks/cluster-name" }

locals {
  boundary_arn = "arn:${local.partition}:iam::${local.account_id}:policy/auto-shop/auto-shop-boundary"
  cluster_arn  = "arn:${local.partition}:eks:${var.aws_region}:${local.account_id}:cluster/${local.cluster_name}"
  isolated_subnet_ids = split(",", data.aws_ssm_parameter.rds_subnet_ids.value)  # StringList vem separado por vírgula
  db_names = { for env in var.environments : env => "autoshop_${env}" }
}
```

**IAM neste root — a única role que este repo cria:**

```hcl
data "aws_iam_policy_document" "pod_identity_trust" {
  statement {
    actions = ["sts:AssumeRole", "sts:TagSession"]
    principals { type = "Service", identifiers = ["pods.eks.amazonaws.com"] }
    condition { test = "ArnEquals", variable = "aws:SourceArn", values = [local.cluster_arn] }
    condition { test = "StringEquals", variable = "aws:SourceAccount", values = [local.account_id] }
  }
}
resource "aws_iam_role" "db_bootstrap" {
  name                 = "auto-shop-staging-db-bootstrap"
  path                 = "/auto-shop/"       # OBRIGATÓRIO: deploy role só cria role sob esse path
  permissions_boundary = local.boundary_arn  # OBRIGATÓRIO: iam:CreateRole é condicionado a iam:PermissionsBoundary
  assume_role_policy   = data.aws_iam_policy_document.pod_identity_trust.json
}
```

Política **inline** (`aws_iam_role_policy`), não managed — o `AttachOnlyApprovedPolicies` só permite `policy/auto-shop/*`, `AmazonEKS*`, `AmazonEC2ContainerRegistryReadOnly`, `AmazonEBSCSIDriverPolicy`, `CloudWatchAgentServerPolicy`:
- ler: `secretsmanager:GetSecretValue`, `DescribeSecret` no ARN do secret master
- escrever: `secretsmanager:PutSecretValue`, `DescribeSecret` nos 4 secrets de app

O Job **não** precisa de `ssm:GetParameter` — host/port/dbname vêm por env do `bootstrap-db.sh`.

```hcl
resource "aws_eks_pod_identity_association" "db_bootstrap" {
  cluster_name    = local.cluster_name
  namespace       = "auto-shop-ops"
  service_account = "auto-shop-db-bootstrap"
  role_arn        = aws_iam_role.db_bootstrap.arn
}
```

`auto-shop-ops` já existe e `gh-deploy-database-infra` já tem `AmazonEKSEditPolicy` nele. A association aceita namespace/SA como string, então pode ser criada antes da ServiceAccount existir.

**Políticas de leitura para consumidores** (atende "IAM de cada consumidor limitado ao ARN exato" da #4 sem este repo dono das roles alheias) — `aws_iam_policy` em `path = "/auto-shop/"`:

| Política | Concede `GetSecretValue`+`DescribeSecret` em | Para |
|---|---|---|
| `auto-shop-staging-db-read-owner` | secret master gerenciado pelo RDS | Job de migrations do `auto-shop-system` |
| `auto-shop-staging-db-read-lambda-hml` | `auto-shop/staging/hml/lambda-auth` | role da função `lambda-auth` hml |
| `auto-shop-staging-db-read-lambda-prd` | `auto-shop/staging/prd/lambda-auth` | idem prd |

Não criar política duplicada para `app_runtime`: a role do ESO no `k8s-infra` já tem grant inline em `app-runtime-*`. Isso é wildcard restrito de nome/sufixo e não ARN literal: registrar o tradeoff frente ao aceite “ARN exato” da #4. Se o avaliador exigir ARN literal para ESO, coordenar ajuste no k8s-infra, fora da propriedade deste plano; não declarar esse requisito integralmente resolvido sem revisão.

**`outputs.tf`:** `db_host`, `db_port`, `db_security_group_id`, `db_names`, `runtime_secret_arns`, `lambda_secret_arns`, `owner_secret_arn`, `bootstrap_role_arn`, `ssm_parameters`. **Nenhum output com senha, `DATABASE_URL` ou valor de secret** — só ARNs e nomes. Não publicar conteúdo secreto nem depender de sensitive para escondê-lo; sensitive só altera a exibição e não evita persistência em state.

Possíveis exceções para `.checkov.yaml`: confirmar os IDs contra a versão instalada e adicionar somente achados efetivos, de preferência por recurso, com justificativa ligada ao ADR e testes delimitando a exceção; **não** copiar esta lista inteira nem suprimir em bloco:

```yaml
framework: [terraform]
skip-check:
  - CKV_AWS_157   # Single-AZ: staging efêmero, dados sintéticos (ADR-0071 rev. 2026-10-25)
  - CKV_AWS_293   # deletion_protection=false: teardown tem que funcionar no mesmo dia
  - CKV_AWS_129   # sem export de logs p/ CloudWatch: custo; slow query ainda vai p/ log do RDS
  - CKV_AWS_118   # sem enhanced monitoring: custo + exigiria role IAM extra
  - CKV_AWS_353   # sem Performance Insights
  - CKV_AWS_354   # (consequência do acima)
  - CKV_AWS_161   # auth por senha, não IAM DB auth: as 3 identidades são roles PostgreSQL
  - CKV_AWS_149   # Secrets Manager na chave gerenciada AWS: sem CMK em PendingDeletion pós-teardown
  - CKV2_AWS_57   # sem rotação automática: credenciais recriadas por sessão e destruídas no teardown
  - CKV2_AWS_34   # contrato SSM guarda só IDs/ARNs não secretos por design
```

### Passo 6 — SQL + Job de bootstrap — #4
Ver §5. Entregáveis: `sql/00-bootstrap.sql`, `sql/10-lambda-grants.sql`, `scripts/bootstrap-db.sh`.

**Aceite local (sem AWS):** um `docker run --rm postgres:16-alpine` aplica `00-bootstrap.sql` **duas vezes** (idempotência) e então assere, conectado como cada role:
- `app_runtime_hml` → `CREATE TABLE t(i int)` **falha** com `42501`
- `app_runtime_hml` → `SELECT/INSERT/UPDATE/DELETE` em tabela do owner **passam**
- `lambda_auth_hml` → `UPDATE customers ...` e `INSERT INTO customers` **falham**
- `lambda_auth_hml` → a query exata da Lambda **passa**; `SELECT name, email FROM customers` **falha** (grant por coluna)
- `app_runtime_hml` conectando em `autoshop_prd` **falha** (sem `CONNECT`)

Antes das asserções por tabela, criar fixtures como owner (simulando Alembic) e aplicar `10-lambda-grants.sql` duas vezes. Repetir os testes em prd e testar isolamento nos dois sentidos, CREATE DATABASE negado, SELECT * e colunas extras negados, sequências permitidas ao runtime e ausência de memberships que permitam SET ROLE privilegiado. NOINHERIT sozinho não impede SET ROLE. Revogar TEMP de PUBLIC nos databases de aplicação se o critério é ausência completa de DDL, incluindo tabelas temporárias.

Isso vira um job `sql` no `ci.yml` com `services: postgres:16-alpine` — sem credenciais AWS, roda em todo PR. Testes de fixtures do guard, scripts e vazamento em erro são escritos antes da implementação. Medir ≥80% de cobertura do código executável de scripts e 100% dos ramos críticos de autorização/sanitização; documentar ferramenta e métrica. Terraform não tem cobertura de linhas equivalente: usar matriz de invariantes e testes de cada recurso/validação, sem alegar 80% apenas por contar módulos.

### Passo 7 — `apply.yml`/`destroy.yml`/`smoke.sh`/`orphans.sh` — #1, #3

**`apply.yml`** — estrutura do `k8s-infra`: `push:[main]` + `workflow_dispatch`; ambos validam `STAGING_ACTIVE=true` e sessão especificamente autorizada, sem dispatch como bypass; `environment: staging`; `concurrency: staging-database`; **preflight** com 2 checagens que falham rápido: (1) `aws iam get-policy` da boundary — se faltar, o bootstrap do `k8s-infra` não está aplicado e o `iam:CreateRole` falharia **depois** do RDS já existir; (2) os 5 parâmetros SSM obrigatórios + `aws eks describe-cluster`. Depois gerar plano salvo, validar pelo guard e aplicar esse plano (capturar stdout **e stderr** em arquivo privado e emitir apenas status fixo; apagar temporários), `./scripts/bootstrap-db.sh bootstrap`, `./scripts/smoke.sh | tee -a "$GITHUB_STEP_SUMMARY"`.

**`destroy.yml`** — como o do `k8s-infra`, com uma mudança deliberada:
- `workflow_dispatch` (input `confirm == "destroy"`) **+ `schedule: cron "30 1 * * *"`**.
- **01:30 UTC, não 02:00.** O destroy noturno do `k8s-infra` é `0 2 * * *`. Se os dois disparam juntos eles **corrida**: o `k8s-infra` tenta apagar a VPC/subnets enquanto as ENIs do RDS ainda ocupam as subnets isoladas, o destroy dele falha, e a sessão fica meio-desmontada **ainda cobrando**. 30 min antes **não torna a ordem determinística**: Actions pode atrasar e o RDS demorar mais de meia hora. Exigir session-down coordenado que espere destroy+orphans de DB antes do destroy da rede, com gate correspondente no k8s-infra. Até esse contrato existir, operador monitora teardown; cron é somente fallback. Documentar nos dois READMEs, fora da propriedade desta tarefa.
- Antes do `terraform destroy`, limpar os resíduos Kubernetes **só se o cluster ainda existir** (mesmo guard `describe-cluster` + `ResourceNotFoundException` do `k8s-infra`): `kubectl -n auto-shop-ops delete job/auto-shop-db-bootstrap configmap/auto-shop-db-bootstrap-sql serviceaccount/auto-shop-db-bootstrap --ignore-not-found`.
- O destroy do `aws_eks_pod_identity_association` chama a API do EKS; se o `k8s-infra` já apagou o cluster, falha. Mitigação primária é a orquestração com espera de conclusão e orphan check. Caso o cluster seja confirmado inexistente por ResourceNotFoundException, inspecionar refresh/estado e usar procedimento revisado de recuperação; não embutir state rm automático nem remover do state recurso AWS ainda existente. AccessDenied/rede devem falhar.
- `./scripts/orphans.sh | tee -a "$GITHUB_STEP_SUMMARY"` — **exit non-zero se sobrou algo cobrável.**

**`scripts/orphans.sh`** (`set -euo pipefail`, shellcheck-clean, exit 1 em qualquer achado/erro de consulta): usar tags Repository/Project e IDs/ARNs capturados antes do destroy para limitar propriedade. Consultar instância original e eventual restore, snapshots manuais/automáticos e backups automatizados retidos pela API própria, subnet/parameter groups, SG, quatro secrets exatos e master exato, policies/role/association e parâmetros SSM de saída por nomes ou listagem de metadados. Não usar GetParametersByPath, não tratar todo rds!db-* da conta como órfão deste repo e não deletar recursos de terceiros. Exclusão de secret é assíncrona: retries com timeout, falhando se pendente. Backend, states e bootstrap IAM persistente são exclusões documentadas.

**`scripts/smoke.sh`** (linhas `PASS`/`FAIL`, exit non-zero em falha):
1. `describe-db-instances`: `available`, `PubliclyAccessible == false`, `MultiAZ == false`, `EngineVersion` 16.15, `StorageEncrypted`, `BackupRetentionPeriod == 1`, `DeletionProtection == false`
2. subnets do subnet group == `rds-isolated-subnet-ids`
3. SG do RDS com exatamente 2 ingress, ambos por SG referenciado, zero `0.0.0.0/0`
4. os parâmetros SSM da §4 existem e nenhum é `SecureString`
5. os 4 secrets existem e **têm ao menos uma versão** (prova que o Job publicou) — sem imprimir valor
6. verificar payload e TLS dentro do Job autorizado, usando referência de secret resolvida em runtime, sem ler valores no shell do agente; provar conexão verify-full e rejeição de CA/hostname errado, não só presença de texto no DSN
7. conectividade in-cluster: Job com SA autorizada e security context restricted roda testes de privilégios em **hml e prd**, após Alembic e grants; trap apaga o Job. Smoke inicial pré-migrations valida apenas configuração/rede/TLS/bootstrap, nunca exige tabelas ainda ausentes
8. a inalcançabilidade externa (#2 Cenário 2) é **evidência por configuração**, não teste vivo — um timeout de runner não prova nada em tempo limitado. Asserir `PubliclyAccessible == false` e que as route tables das subnets do RDS não têm rota `0.0.0.0/0`. Documentar a substituição no README.

### Passo 8 — README + CHANGELOG (local) — #1, #5
Espelhar os títulos do README do `k8s-infra`, em português: tabela de repos, Tecnologias, Arquitetura (diagrama), Estrutura, **Contrato publicado (SSM)** com a tabela da §4 e os leitores, **Segredos criados**, Execução (bloco ordenado incluindo a dependência `k8s-infra` primeiro), CI/CD, **Custo**, Segurança: controles implementados, **Decisões de segurança aceitas** (um bullet por skip do checkov), Limitações conhecidas, e **Política de compatibilidade**: renomear/remover qualquer parâmetro SSM ou nome de secret exige label `breaking-change` no PR + entrada no CHANGELOG (#5). Criar o label (`gh label create`).

Tabela de custo (us-east-1, on-demand):

| Item | US$/h |
|---|---|
| RDS `db.t4g.micro` PostgreSQL Single-AZ | 0,016 |
| 20 GiB gp3 (US$ 0,115/GiB-mês) | 0,0032 |
| Backups, retenção 1 dia | depende de franquia e restore; revalidar |
| 4 segredos no Secrets Manager (US$ 0,40/mês, rateado) | 0,0022 |
| Secret master gerenciado pelo RDS | 0,0006 |
| **Total deste repositório** | **~0,022** |

Referência histórica do plano geral/Price List us-east-1 de 2026-10-25: sessão de 5 h ≈ **US$ 0,11** de parcelas fixas DB; não é cotação atual nem garantia de gratuidade. Revalidar tarifas oficiais/Calculator antes de apply. Incluir requests Secrets Manager, tráfego/NAT, storage/backup excedente e instância temporária de restore; CPU credits se aplicáveis. Conferir composição antes de somar à estimativa agregada do k8s-infra para não contar RDS duas vezes. ADR e Fase 1 têm estimativas históricas que precisam ser recalculadas para On-Demand e para o escopo atual de CloudFront/S3, domínio, ACM e ambos os WAFs. Os budgets de US$ 1/5/10 são alertas; não há gatilho de pausa de US$ 20 configurado e budgets não limitam nem desligam recursos.

## 3. Ordem de dependência e necessidade de sessão

| Passo | Precisa AWS viva? | Bloqueado por |
|---|---|---|
| 0 Skeleton | não | — |
| 1 `ci.yml` + `plan-guard.sh` | não (job plan se auto-skipa) | 0 |
| 2 `db-network` | não (`mock_provider`) | 0 |
| 3 `db-secrets` | não | 0 |
| 4 `db-instance` | não | 0 |
| 5 Root + IAM + SSM | **plan** precisa `k8s-infra` aplicado; **apply** precisa sessão | 2,3,4 |
| 6 SQL + script | não para os testes SQL (Docker); sim ponta-a-ponta | 5 |
| 7 apply/destroy/smoke/orphans | sim, para provar | 5,6 |
| 8 README/CHANGELOG | não | todos |

Passos 0–4, os testes SQL do 6, e o 8 são **inteiramente locais**. Só o `plan` do 5 e a prova do 7 precisam de sessão.

**Runbook da sessão** (ADR-0064 exige autorização explícita por apply, incluindo conta/região/recursos/custo; até 5 h incluindo teardown, com margem de segurança antes do limite e sem pernoite):

```
k8s-infra apply foundation → k8s-infra apply platform (cria auto-shop-ops)
  → database-infra plan salvo + guard → apply → bootstrap-db.sh bootstrap → smoke inicial
  → auto-shop-system: migrations Alembic (identidade owner)
  → database-infra: bootstrap-db.sh grants (grants por coluna do lambda_auth)
  → smoke completo nos dois databases → prova de restore → remover restore e seus backups
  → parar consumidores/Lambda → database-infra destroy + orphans aprovado
  → k8s-infra platform/foundation destroy + orphans global (com espera entre repos)
```

`auto-shop-ops` tem que existir antes do Job; é criado pelo stack **platform** do `k8s-infra`, então o apply do database-infra pode vir antes do platform, mas o `bootstrap-db.sh` não.

## 4. Nomes exatos

### Parâmetros SSM publicados (todos `String`, tier `Standard`, `us-east-1`)

| Parâmetro | Valor | Leitor |
|---|---|---|
| `/auto-shop/staging/database/host` | `module.instance.address` | deploy do `k8s-infra`/`lambda-auth` |
| `/auto-shop/staging/database/port` | `"5432"` | idem |
| `/auto-shop/staging/database/security-group-id` | id do SG do RDS | `lambda-auth` (validação de rede) |
| `/auto-shop/staging/database/names/hml` | `autoshop_hml` | materialização de config app+Lambda |
| `/auto-shop/staging/database/names/prd` | `autoshop_prd` | idem |
| `/auto-shop/staging/database/secrets/runtime-hml-arn` | ARN de `auto-shop/staging/hml/app-runtime` | deploy de ExternalSecret do `auto-shop-system` |
| `/auto-shop/staging/database/secrets/runtime-prd-arn` | ARN de `.../prd/app-runtime` | idem |
| `/auto-shop/staging/database/secrets/lambda-hml-arn` | ARN de `.../hml/lambda-auth` | `lambda-auth` |
| `/auto-shop/staging/database/secrets/lambda-prd-arn` | ARN de `.../prd/lambda-auth` | idem |
| `/auto-shop/staging/database/secrets/owner-arn` | ARN do secret master (`rds!db-…`) | role do Job de migrations |
| `/auto-shop/staging/database/iam/owner-read-policy-arn` | ARN de `policy/auto-shop/auto-shop-staging-db-read-owner` | `auto-shop-system` anexa na role de migrations |
| `/auto-shop/staging/database/iam/lambda-read-policy-arn/hml` | ARN de `…db-read-lambda-hml` | `lambda-auth` |
| `/auto-shop/staging/database/iam/lambda-read-policy-arn/prd` | ARN de `…db-read-lambda-prd` | idem |

Os 10 primeiros são exatamente a lista da #5. Os 3 `iam/` são **proposta aditiva além da #5**, a acordar com consumidores — tornam o "IAM limitado ao ARN exato" da #4 implementável entre repos (ver §6 item 13).

Sem `database/name` (singular), sem `db_proxy_endpoint`, sem `DATABASE_URL`, sem `SecureString`, sem `migrations-arn`.

### Secrets criados

| Secret | Criado por | Versão escrita por | Payload |
|---|---|---|---|
| `rds!db-<resource-id>` | RDS (`manage_master_user_password`) | RDS | `{username,password}` gerenciado; apagado com a instância |
| `auto-shop/staging/hml/app-runtime` | Terraform (só metadata) | Job | JSON abaixo |
| `auto-shop/staging/prd/app-runtime` | Terraform (só metadata) | Job | idem |
| `auto-shop/staging/hml/lambda-auth` | Terraform (só metadata) | Job | idem |
| `auto-shop/staging/prd/lambda-auth` | Terraform (só metadata) | Job | idem |

Os 4: `recovery_window_in_days = 0`, chave `aws/secretsmanager`, **nenhum `aws_secretsmanager_secret_version` no Terraform**.

```json
{
  "username": "app_runtime_hml",
  "password": "<32 chars [A-Za-z0-9]>",
  "host": "auto-shop-staging.xxxx.us-east-1.rds.amazonaws.com",
  "port": "5432",
  "dbname": "autoshop_hml",
  "sslmode": "verify-full",
  "DATABASE_URL": "postgresql://app_runtime_hml:<password>@<host>:5432/autoshop_hml?sslmode=verify-full"
}
```

`DATABASE_URL` leva `sslmode=verify-full` mas **sem `sslrootcert`** — o ADR manda distribuir o bundle CA como arquivo de runtime e apontar por `PGSSLROOTCERT`/`sslrootcert` por runtime. Gerar senha com CSPRNG e validar tamanho exato (por exemplo, 32 caracteres de alfabeto permitido); testar sob pipefail. Filtrar base64 de 24 bytes pode produzir menos de 32 caracteres e pipelines com head podem falhar por SIGPIPE. Mesmo com alfabeto restrito, usar quoting seguro. A senha master gerenciada pode conter caracteres especiais: tratar escape de pgpass e DSN sem alterá-la.

## 5. As três identidades: SQL e empacotamento do Job

| Identidade | Role PostgreSQL | Credencial | Privilégios |
|---|---|---|---|
| `owner` | `autoshop_owner` (master RDS) | secret gerenciado pelo RDS | dono dos 2 databases e do `schema public`; DDL completo — bootstrap + Alembic |
| `app_runtime` | `app_runtime_hml`, `app_runtime_prd` | `auto-shop/staging/<env>/app-runtime` | só DML no próprio database; **sem** `CREATE` em `schema public` |
| `lambda_auth` | `lambda_auth_hml`, `lambda_auth_prd` | `auto-shop/staging/<env>/lambda-auth` | `SELECT` por coluna em exatamente 4 colunas |

As **colunas exatas** do `lambda_auth` vêm de `pos/lambda-auth/src/lambda_auth/adapters/postgres_customer_repository.py`:

```sql
SELECT customers.id FROM customers
  JOIN customer_documents ON customer_documents.customer_id = customers.id
 WHERE customer_documents.document = %s AND customers.status = %s LIMIT 1
```

→ `customers(id, status)` e `customer_documents(customer_id, document)`. Nada mais.

### `sql/00-bootstrap.sql` — fase `bootstrap`, antes das migrations

Idempotente, sem dependência de tabela. Por ambiente, com `\set` injetado (ver empacotamento):

```sql
\set ON_ERROR_STOP on
-- 1. Database (CREATE DATABASE não roda em transação nem tem IF NOT EXISTS)
SELECT 'CREATE DATABASE ' || quote_ident(:'dbname') || ' OWNER ' || quote_ident(:'owner_role')
 WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = :'dbname') \gexec
-- 2. Roles criadas se ausentes; valores abaixo só na inicialização/recuperação coordenada.
--    Retry normal e fase grants NÃO renovam senhas já publicadas; ver protocolo abaixo.
SELECT 'CREATE ROLE ' || quote_ident(:'app_role') || ' LOGIN'
 WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'app_role') \gexec
SELECT 'CREATE ROLE ' || quote_ident(:'lambda_role') || ' LOGIN'
 WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'lambda_role') \gexec
ALTER ROLE :"app_role"    WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT
     NOREPLICATION NOBYPASSRLS CONNECTION LIMIT 20 PASSWORD :'app_pw';
ALTER ROLE :"lambda_role" WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT
     NOREPLICATION NOBYPASSRLS CONNECTION LIMIT 10 PASSWORD :'lambda_pw';
-- 3. Nível database: revoga o default do PUBLIC, concede CONNECT só às 2 roles do ambiente.
--    É isso que faz app_runtime_hml não alcançar autoshop_prd.
REVOKE ALL ON DATABASE :"dbname" FROM PUBLIC;
GRANT CONNECT ON DATABASE :"dbname" TO :"app_role", :"lambda_role";
```

Depois **reconectar no database novo** (`\connect :dbname`, ainda como `autoshop_owner`):

```sql
ALTER SCHEMA public OWNER TO :"owner_role";
REVOKE ALL ON SCHEMA public FROM PUBLIC;
-- app_runtime: USAGE mas NÃO CREATE -> CREATE TABLE falha com 42501
GRANT USAGE ON SCHEMA public TO :"app_role";
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES    IN SCHEMA public TO :"app_role";
GRANT USAGE, SELECT                  ON ALL SEQUENCES IN SCHEMA public TO :"app_role";
-- Tabelas que o Alembic criar DEPOIS precisam ser alcançáveis sem rodar isto de novo:
ALTER DEFAULT PRIVILEGES FOR ROLE :"owner_role" IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO :"app_role";
ALTER DEFAULT PRIVILEGES FOR ROLE :"owner_role" IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO :"app_role";
-- lambda_auth: só USAGE no schema. Grants por coluna precisam das tabelas -> fase `grants`.
GRANT USAGE ON SCHEMA public TO :"lambda_role";
```

`ALTER DEFAULT PRIVILEGES` é o ponto central: `app_runtime` ganha DML automaticamente em toda tabela que o Alembic criar depois, sem segunda reconciliação e sem nunca receber DDL.

### `sql/10-lambda-grants.sql` — fase `grants`, depois do Alembic

```sql
\set ON_ERROR_STOP on
\connect :dbname
GRANT SELECT (id, status)            ON TABLE public.customers          TO :"lambda_role";
GRANT SELECT (customer_id, document) ON TABLE public.customer_documents TO :"lambda_role";
-- Prova o negativo no próprio script (o Job falha se a asserção falhar):
DO $$
BEGIN
  IF has_table_privilege(current_setting('autoshop.lambda_role'), 'public.customers', 'UPDATE')
  OR has_table_privilege(current_setting('autoshop.lambda_role'), 'public.customers', 'INSERT')
  OR has_column_privilege(current_setting('autoshop.lambda_role'), 'public.customers', 'email', 'SELECT')
  THEN RAISE EXCEPTION 'lambda_auth privilege escalation detected';
  END IF;
END $$;
```

Antes do DO, inicializar o setting não secreto com `SELECT set_config('autoshop.lambda_role', :'lambda_role', false)` na mesma conexão; caso contrário current_setting falha. Revogar grants indevidos preexistentes antes de conceder a allowlist: GRANT sozinho não reconcilia escalada. Reexecutar grants deve preservar credenciais. O self-check do `app_runtime` (`has_schema_privilege(app_role,'public','CREATE')` falso) mora aqui também.

### Empacotamento e invocação do Job

**Sem provider `kubernetes` e sem provider `postgresql`.** Duas razões, ambas decisivas:
1. ADR-0071 e a #4 proíbem o provider PostgreSQL e proíbem senha chegando a state/plan/log.
2. **`gh-plan-database-infra` não tem access entry no EKS.** O `foundation` do `k8s-infra` cria entries para `gh-deploy-k8s-infra`, `gh-plan-k8s-infra`, `gh-deploy-auto-shop-system` e `gh-deploy-database-infra` — **não** para `gh-plan-database-infra`. Um root com provider `kubernetes` falharia o `terraform plan` em todo PR com erro de autorização.

O Job é dirigido por **`scripts/bootstrap-db.sh`**, rodado pelo `apply.yml` como `gh-deploy-database-infra` (que tem `AmazonEKSEditPolicy` em `auto-shop-ops`):

```
./scripts/bootstrap-db.sh bootstrap   # fase 1, no apply.yml
./scripts/bootstrap-db.sh grants      # fase 2, após as migrations do auto-shop-system
```

O script (`set -euo pipefail`, **nunca `set -x`**, shellcheck-clean): lê host/port/dbnames/ARNs/cluster do SSM (nunca de `terraform output`, pra funcionar standalone); `aws eks update-kubeconfig`; aplica ServiceAccount `auto-shop-db-bootstrap` (casando a Pod Identity association) e ConfigMap `auto-shop-db-bootstrap-sql` (`--from-file=sql/`); `delete job --ignore-not-found --wait` e `apply` do Job renderizado; espera conclusão com timeout compatível com deadline; em falha emite somente status fixo/código e sai non-zero, sem imprimir kubectl logs bruto nem confiar em regex de password; `trap` apaga Job/ConfigMap/SA na saída.

**Forma do Pod** — 3 containers, só imagens públicas, sem build e portanto sem ECR neste repo. A ordem é garantida pelo Kubernetes: **init containers rodam em sequência e todos têm que passar antes do container principal** — mas isso não dá atomicidade entre PostgreSQL e Secrets Manager; ver protocolo de retry abaixo.

| Container | Imagem | Faz |
|---|---|---|
| init 1 `fetch` | imagem com AWS CLI, ferramentas verificadas e mecanismo autorizado de resolução de secrets (fixar digest) | resolve secret owner em runtime via Pod Identity, sem valor no agente/manifest; gera as 4 senhas com CSPRNG; calcula verificadores SCRAM-SHA-256 offline; escreve `/work/vars.sql` com verificadores, `/work/pgpass` (chmod 600) e `/work/payload-*.json` com senhas em claro apenas para publicação |
| init 2 `psql` | `public.ecr.aws/docker/library/postgres:16-alpine` (fixar digest) | CA oficial empacotada ou baixada/verificada com ferramentas presentes; `PGSSLROOTCERT=... PGSSLMODE=verify-full PGPASSFILE=...`; por ambiente aplica SQL sem eco e recebe somente os verificadores por stdin, com ON_ERROR_STOP e stdout/stderr capturados privadamente |
| main `publish` | mesma imagem aws-cli | `PutSecretValue` dos 4 secrets a partir de `/work/payload-*.json`, depois destrói `/work` |

`volumes: [{ name: work, emptyDir: { medium: Memory, sizeLimit: 1Mi } }]` — senhas só em tmpfs, nunca em disco de node, log ou Terraform. Testar limite real com payloads/CA e fsGroup/UID compatíveis para leitura entre containers, sem permissões mundiais. Confirmar ferramentas disponíveis em cada imagem (jq/openssl/curl não são garantidos pela imagem aws-cli).

**Resolução segura obrigatória:** AGENTS exige referências `{{resolve:secretsmanager:secret-id:SecretString:json-key}}` via `asm-exec`; validar esse mecanismo na imagem antes de implementar o fetch. Não executar `get-secret-value`, `batch-get-secret-value` ou daemon Secrets Manager no shell do agente, smoke ou runbook. Se a ferramenta não estiver disponível, bloquear essa integração e coordenar solução aderente, sem contornar a regra. O runtime autorizado escreve payloads sem devolver valores ao agente. A skill local chamada `aws-secrets-manager` não estava disponível no catálogo; a orientação equivalente foi obtida do catálogo oficial AWS, sem instalar skills.

**Protocolo de idempotência e falha:** credenciais novas a cada sessão não significa resetá-las em toda reexecução. Definir bootstrap inicial, marcador de conclusão sem segredo e recuperação; retry comum preserva credencial já publicada ou bloqueia operação até modo de recuperação explícito. PostgreSQL e Secrets Manager não têm transação conjunta: testar falha após ALTER ROLE, PutSecretValue parcial e retry. Se a reconciliação exigir ler os quatro secrets de app, conceder somente esses ARNs à role bootstrap e documentar esse acesso; não ampliar leitores normais. Nenhum consumidor é liberado antes da correspondência de todos os payloads com as roles. A fase **grants** usa caminho separado, sem geração/reset/publicação de credenciais.

Capturar stdout e stderr de psql/AWS em arquivos temporários privados; descartar ao sair e emitir mensagens fixas. Não usar psql echo nem logging de statements que incluam senha. O SQL e o harness local agora recebem um verificador SCRAM-SHA-256 por stdin/arquivo privado, sem `psql -v password=...`; o container `fetch` ainda precisa calcular o mesmo formato sem expor o valor. Testes com credencial-canário sintética precisam provar ausência em stdout, stderr e artefatos para sucesso e falhas. O fluxo operacional ainda não foi implementado: `scripts/bootstrap-db.sh` permanece fail-closed até validar o resolver aprovado e o protocolo de idempotência/recuperação.

**Restrições do ambiente (verificadas contra o platform do `k8s-infra`):**
- **Pod Security `restricted`** está enforced em `auto-shop-ops`. Todo container precisa `runAsNonRoot: true`, `runAsUser`, `allowPrivilegeEscalation: false`, `capabilities.drop: ["ALL"]`, `seccompProfile.type: RuntimeDefault`. O `psql` roda bem como uid 70. Para que nenhum arquivo temporário vá ao disco do container, montar o mesmo `emptyDir.medium: Memory` em `/work` e `/tmp` para todos os containers; definir `HOME=/work/home`, `TMPDIR=/work/tmp`, `XDG_CACHE_HOME=/work/cache`, `AWS_CONFIG_FILE=/work/home/.aws/config` e `AWS_SHARED_CREDENTIALS_FILE=/work/home/.aws/credentials`. Colocar CA, SQL, `pgpass`, payloads e capturas de stdout/stderr em `/work`; criar diretórios com ownership/modo compatíveis com o UID restrito e nunca gravar credenciais estáticas.
- **NetworkPolicy**: `auto-shop-ops` tem default-deny + `allow-dns` + `allow-egress-postgres` (5432 para os CIDRs isolados) + `allow-egress-https` (443 para `0.0.0.0/0` exceto o CIDR da VPC) + `allow-same-namespace`. Não afirmar suficiência sem prova: Pod Identity usa agente link-local `169.254.170.23` em 80/2703, e a referência exclui `169.254.0.0/16` do HTTPS. Testar acesso ao agente com VPC CNI strict. Se bloqueado, coordenar policy mínima no k8s-infra para os Pods necessários, mantendo IMDS bloqueado; não abrir todo link-local ou remover default-deny.
- `LimitRange` do namespace: default 100m/128Mi request, 500m/512Mi limit, max 1Gi — ok; declarar requests pequenos explicitamente.
- `backoffLimit: 1`, `activeDeadlineSeconds: 420`, `ttlSecondsAfterFinished: 300`, `restartPolicy: Never`.

## 6. Riscos e decisões humanas

### Pode deixar recurso cobrável órfão
1. **`delete_automated_backups`** — declarar explicitamente `true`. Com `skip_final_snapshot` e retenção 1 dia, esquecer isso deixa backups cobrando depois da instância ir. `orphans.sh` checa `--snapshot-type automated`.
2. **`recovery_window_in_days` default é 30 no Secrets Manager.** Secret em recuperação bloqueia recriar o mesmo nome na sessão seguinte (`InvalidRequestException: scheduled for deletion`). `0` é obrigatório nos 4. `orphans.sh` precisa de `--include-planned-deletion`.
3. **Corrida do cron noturno com o `k8s-infra`** (ver Passo 7). Mitigação: session-down aguarda conclusão DB+orphans antes da rede; horários 01:30/02:00 são fallback e não estabelecem dependência entre workflows. Esse gate requer integração em outro repo antes de confiar no destroy automático.
4. Apply falho no meio só deixa RDS fora do state se a escrita do state falhar; `use_lockfile` + root único minimizam, e `orphans.sh` consulta a AWS (não o state), então pega.
5. **Destroy do `aws_eks_pod_identity_association` depende de cluster vivo.** Se o `k8s-infra` cair primeiro, a remoção da association pode falhar e deixar o teardown incompleto. Ordenar por dependência entre workflows e aplicar o procedimento revisado de recuperação do Passo 7 somente após confirmar ausência; não usar state rm como limpeza automática.
6. **Compatibilidade de classe/storage/versão deve ser verificada antes da sessão.** O resultado da Fase 1 registra conta Paid; elegibilidade Free não é o critério atual. Consultar metadados de engine e opções orderable para a combinação aprovada. Uma alternativa como `db.t3.micro` exige nova verificação de disponibilidade/preço, atualização dos testes/guard e aprovação; não é fallback automático.

### Pode vazar credencial
7. `plan-summary.sh` imprime só endereços e ações — manter assim; nunca `terraform plan` sem ele no CI, capturar stdout e stderr de plan/apply em temporário privado, pois redirecionar só stdout não impede vazamento em erro.
8. **Nenhum `data "aws_secretsmanager_secret_version"`.** Além de vazar para o state, `gh-plan-database-infra` tem `GetSecretValue` negado — quebraria todo PR.
9. **Nunca passar senha em linha de comando.** `psql -v pw=…` aparece em `/proc/*/cmdline`. Usar `cat vars.sql script.sql | psql` e `PGPASSFILE`.
10. **Nunca `set -x`** no `bootstrap-db.sh` nem nos shells do Job; não ecoar logs brutos em falha; testar ausência de credencial-canário sintética em stdout/stderr.
11. `gh-plan-*` nega SSM fora de `/auto-shop/*` e `aws/service/*`. Todo `data "aws_ssm_parameter"` daqui está sob `/auto-shop/staging/`, então o plan funciona — mas adicionar qualquer outra leitura quebra o CI de PR silenciosamente.
12. A lição de STS da Fase 1 (`aud`/`sub` só; `repository`/`event_name`/`environment`/`job_workflow_ref` presentes no token mas **não avaliados**) **não se aplica** a este repo — ele não cria trust policy de OIDC do GitHub. Aplica-se à única trust que cria (`pods.eks.amazonaws.com`), onde `aws:SourceArn` fixado no ARN do cluster é condição normal de service principal e funciona.

### Precisa decisão humana — não escolher em silêncio
13. **Resolvido nesta revisão documental:** a tabela de contrato SSM do ADR foi atualizada. Ela distingue os parâmetros publicados por `k8s-infra` dos 13 parâmetros de banco publicados por `database-infra` (hosts, portas, SG, databases, secrets e políticas IAM). O ADR registra três identidades por database (`owner`, `app_runtime`, `lambda_auth`). A compatibilidade entre nomes publicados e consumidores ainda precisa ser verificada nos repositórios antes do apply.
14. **`migrations-arn` → `owner-arn` muda comportamento do `auto-shop-system`.** O Job de migrations dele hoje pega `DATABASE_URL` de `envFrom: secretRef: auto-shop-secrets`, ou seja, o que o ESO sincroniza — e o ESO está escopado só a `app-runtime`, que no modelo novo **não tem DDL**. Logo o Alembic vai falhar com `permission denied for schema public` a menos que o `auto-shop-system` passe a buscar o secret `owner` direto (ADR: "O Job de migrations lê o `owner` direto do Secrets Manager por role própria"). Exige, lá: role Pod Identity para a SA do migrate com `auto-shop-staging-db-read-owner` anexada, e um passo que monta `DATABASE_URL` a partir do secret. **Fora do escopo do `database-infra`, mas bloqueia a sessão ponta-a-ponta — precisa de issue própria no `auto-shop-system`.** Este plano faz a metade dele: cria a política, publica o ARN dela e do secret owner, documenta o requisito no README.
15. **Quem cria a Pod Identity association da SA de migrations?** Recomendação: o `auto-shop-system` cria a role + association e anexa a política publicada. Confirmar.
16. **Ordenação da fase `grants`.** Grants por coluna do `lambda_auth` não podem existir antes do Alembic criar `customers`/`customer_documents`. O plano separa o Job em `bootstrap` e `grants`. Quem dispara o `grants` — `workflow_dispatch` aqui ou `repository_dispatch` do pipeline do `auto-shop-system` — é decisão humana. Mais simples para o prazo: input `phase: bootstrap|grants` no `apply.yml`, rodado manualmente pelo runbook.
17. **A issue #2 nunca recebeu bloco "Escopo vigente".** O Cenário 1 dela ainda diz que a VPC vem "exposta via `terraform_remote_state`", contradizendo o cabeçalho de 2026-10-23 da própria issue e o ADR. Tratar o cabeçalho como autoritativo (SSM, sem remote state) e corrigir o corpo da issue.
18. **Restore dentro de 5 h precisa de procedimento e orçamento próprios.** Retenção configurada não prova restauração. Escolher janela UTC de backup dentro da sessão; verificar primeiro backup e LatestRestorableTime, inserir marcador sintético, restaurar um ponto recuperável em instância temporária privada com SG/subnets/TLS equivalentes e confirmar marcador via Job autorizado. Aprovar custo/ownership/cleanup do restore antes de criar; destruir instância de teste e backups/snapshots antes do encerramento do original. Reservar margem para teardown dentro das 5 h. Se não houver ponto recuperável em tempo, registrar aceite pendente e replanejar, sem reter recursos durante a noite.
19. **Performance Insights** era exigido pelo texto antigo da #3 ("para embasar o HPA") e foi retirado pelo escopo atual. O plano desabilita (custo + CMK). Se o vídeo de HPA/escalabilidade precisar de métrica de banco, dizer agora.
20. **Pin do minor resolvido pela evidência fornecida:** API DescribeDBEngineVersions em us-east-1 identificou **16.15** como PostgreSQL 16 mais recente. Fixar esse minor e registrar data/fonte no README. Revalidar antes de executar por consulta de metadados, sem atualizar major automaticamente.

## 7. Definition of done

**#1 Bootstrap:** `modules/` + `envs/staging/database/`, sem `envs/production/`; backend com a chave exata e `use_lockfile`, sem DynamoDB, segundo apply concorrente falha no lock; versões pinadas e `.terraform.lock.hcl` commitado; CI de PR com fmt/validate/test/tflint/checkov/shellcheck/testes SQL/plan+plan-guard sem valor sensível em log; só OIDC, roles existentes reusadas e nunca modificadas, environment `staging` restrito a `main` e asserido pelo CI; README, branch protection, `soat-architecture` read.

O teste de lock S3 deve ocorrer em sessão controlada autorizada; concurrency do Actions não substitui essa prova. Apply/destroy usam o mesmo grupo de concurrency com cancel-in-progress=false e timeout; destroy não pode ser bloqueado por STAGING_ACTIVE=false se houver órfãos. CI de PR não usa pull_request_target para executar código não confiável com privilégio de deploy.

**#2 Rede/SG:** subnet group só com as 2 subnets isoladas em 2 AZs sem rota default; ingress 5432 só dos 2 SGs por referência, zero CIDR, zero egress; `publicly_accessible = false` asserido por `terraform test`, `plan-guard.sh` e `smoke.sh`; consumo por SSM e zero ocorrências de `terraform_remote_state` (guard `grep -r` no CI).

**#3 RDS:** PG16 (minor pinado), `db.t4g.micro`, 20 GiB gp3, Single-AZ, subnets isoladas, sem IP público; `storage_encrypted` sem `kms_key_id`; parameter group com `rds.force_ssl=1` e `log_min_duration_statement`; retenção 1; `deletion_protection=false`, `skip_final_snapshot=true`, `delete_automated_backups=true` e `orphans.sh` verde pós-destroy; `manage_master_user_password=true` e nenhum argumento `password`; sem RDS Proxy nem Multi-AZ (asserido); custo por sessão no README.

**#4 Credenciais:** `owner` = master do RDS, ARN publicado, valor só via `auto-shop-staging-db-read-owner`; `app_runtime_{hml,prd}` com DML no próprio database e sem DDL, secret JSON em nome compatível com ESO; `lambda_auth_{hml,prd}` com `SELECT` por coluna nas 4 colunas; Job efêmero in-VPC cria tudo idempotentemente, gera senhas em runtime e grava por `PutSecretValue`; sem provider PostgreSQL; análise semântica sem argumento/gerador/data source que materialize senha, sem DSN em outputs, e teste canário de logs; a palavra password em manage_master_user_password é legítima; testes negativos passam no Docker (todo PR) e in-cluster (`smoke.sh`); uma política IAM por consumidor no ARN exato, publicada no SSM.

**#5 Contrato:** os 13 parâmetros atuais com os nomes exatos, documentados com publicador/tipo/leitor; consumo por nome/ARN exato, sem `terraform_remote_state` nem `GetParametersByPath`; sem `db_proxy_endpoint`; sem `DATABASE_URL` em SSM ou output (asserido); label `breaking-change` criada; seção "Política de compatibilidade" no README; CHANGELOG `[Unreleased]` populado.

**Gates externos ainda abertos:** protocolo de commit/publicação do repo vazio; owner no Job de migrations (role/SA/association própria, DSN montado em memória, sem sincronizar master via ESO); escolha do disparo de grants; ferramenta e resolução segura de secrets via `asm-exec`; teste de Pod Identity sob NetworkPolicy strict; revisão do wildcard ESO; integração de session-down com espera entre repos; plano/custo de restore. ADR-0071 e sua tabela SSM foram atualizados na branch local de documentação. O bootstrap do Job continua fail-closed enquanto não houver o resolver `asm-exec` exigido pelo projeto. O adapter Lambda ainda força `sslmode="require"`: lambda-auth deve mudar para verify-full com CA e teste antes de demonstrar o fluxo; não alterar esse código nesta tarefa.

**Prova de sessão (a barra da Fase 1):** uma sessão completa executada — `k8s-infra` apply → `database-infra` apply → `bootstrap-db.sh bootstrap` → smoke inicial → Alembic hml/prd como owner → `bootstrap-db.sh grants` → smoke completo + restore → parar consumidores/Lambda → `destroy.yml` DB → `orphans.sh` DB sem achados → destroy k8s → orphan check global → gasto real registrado com horário e ressalva do atraso de billing. Dono da documentação corrige ADR-0071/tabela SSM em tarefa separada. **Esta revisão documental não executou nem comprovou essa sessão.**

## Arquivos de referência obrigatórios

- `pos/k8s-infra/envs/staging/bootstrap/main.tf` — restrições IAM que todo recurso deste repo precisa satisfazer (path `/auto-shop/`, boundary obrigatória, allow-list de `AttachRolePolicy`, denies do papel de plan)
- `pos/k8s-infra/envs/staging/foundation/main.tf` — o contrato SSM consumido e a access entry `database-deploy` escopando `gh-deploy-database-infra` a `auto-shop-ops`
- `pos/k8s-infra/envs/staging/platform/addons.tf` — escopo `app-runtime-*` da role do ESO, que fixa os nomes dos secrets de runtime
- `pos/k8s-infra/envs/staging/platform/{network_policies,namespaces}.tf` — PSS `restricted` e default-deny + egress PostgreSQL/HTTPS de que o Job depende
- `pos/lambda-auth/src/lambda_auth/adapters/postgres_customer_repository.py` — única fonte autoritativa das 4 colunas do `lambda_auth`
- `auto-shop-system/docs/architecture/decisions/ADR-0071-infraestrutura-cloud-fase-3.md` — escopo de registro; tabela de contrato precisa da correção do item 13
- Issues vigentes: [#1](https://github.com/Software-Architecture-Group-7-FIAP/database-infra/issues/1), [#2](https://github.com/Software-Architecture-Group-7-FIAP/database-infra/issues/2), [#3](https://github.com/Software-Architecture-Group-7-FIAP/database-infra/issues/3), [#4](https://github.com/Software-Architecture-Group-7-FIAP/database-infra/issues/4), [#5](https://github.com/Software-Architecture-Group-7-FIAP/database-infra/issues/5) — lidas integralmente nesta revisão, sem mutação GitHub.
- [AWS: Pod Identity, endpoint do agente e consistência eventual](https://docs.aws.amazon.com/eks/latest/userguide/pod-identities.html) — orientação consultada via AWS MCP; associação pode precisar de retry limitado antes do Job.
- [AWS: TLS PostgreSQL e verificação do servidor](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/UsingWithRDS.SSL.html) e [CA oficial us-east-1](https://truststore.pki.rds.amazonaws.com/us-east-1/us-east-1-bundle.pem).
- [AWS: lifecycle de exclusão de secrets](https://docs.aws.amazon.com/secretsmanager/latest/userguide/manage_delete-restore-secret.html) — exclusão imediata aprovada para dados sintéticos, ainda assíncrona; não justificar com tarifa durante recovery window sem verificação de preços.
