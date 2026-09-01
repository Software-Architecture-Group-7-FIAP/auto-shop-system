# Terraform para Kubernetes

Este diretório oferece um caminho declarativo alternativo ao Kustomize para
gerenciar a stack do Auto Shop em um cluster Kubernetes já existente. Ele não
cria EKS, VPC, IAM, RDS ou qualquer recurso AWS.

## Escopo

O root gerencia namespace, ConfigMap, Job de migration, Deployment, Service,
HPA e Ingress da aplicação. O PostgreSQL é criado apenas quando
`enable_local_database = true`, opção destinada ao ambiente local.

Staging e production continuam usando um banco externo. O Terraform não cria,
atualiza ou lê valores de Secrets: o Secret `auto-shop-secrets` precisa existir
antes do `plan`/`apply` com as chaves exigidas pela aplicação, incluindo
`DATABASE_URL` e `SECRET_KEY`. Para o banco local, também são necessárias
`DB_NAME`, `DB_USER` e `DB_PASSWORD`.

Não aplique Terraform e Kustomize para os mesmos recursos no mesmo namespace.
Escolha um único proprietário por ambiente para evitar drift e conflitos de
ownership.

## Configuração

1. Instale Terraform 1.6 ou superior, `kubectl` e configure um kubeconfig com
   acesso ao cluster desejado. Para desenvolvimento local, Kind ou Docker
   Desktop também são opções válidas.
2. Copie `terraform.tfvars.example` para `terraform.tfvars` e ajuste apenas os
   valores não sensíveis do ambiente.
3. Crie `auto-shop-secrets` por um mecanismo externo e seguro. Nunca coloque
   credenciais no arquivo `.tfvars` versionado.

O provider usa `kubeconfig_path` e `kube_context` quando informados; quando
omitidos, usa a configuração padrão do Kubernetes. O arquivo de state local,
planfiles e tfvars reais são ignorados pelo Git.

## Comandos

Use `-backend=false` apenas para validação sem backend. Para aplicar recursos,
use `terraform init` normal antes do primeiro `plan` ou `apply`.

```bash
terraform -chdir=infra init
terraform -chdir=infra fmt -check -recursive
terraform -chdir=infra validate
terraform -chdir=infra plan -var-file=terraform.tfvars
```

Para validar sem configurar backend:

```bash
terraform -chdir=infra init -backend=false
```

Para o ambiente local, habilite explicitamente o banco:

```bash
terraform -chdir=infra plan \
  -var-file=terraform.tfvars \
  -var=environment=local \
  -var=enable_local_database=true
```

`terraform apply` deve ser executado somente depois da revisão do plano e com
o contexto Kubernetes confirmado por `kubectl config current-context`.

### PowerShell e primeiro ambiente local

Em um namespace novo, o Secret só pode ser criado depois que o Namespace
existir. Faça um bootstrap somente do Namespace, crie o Secret externamente e
depois execute o apply completo. O array abaixo evita que o PowerShell divida
endereços Terraform ou argumentos com `=`:

```powershell
$namespace = "auto-shop-tf-test"
$kubeconfig = Join-Path $env:USERPROFILE ".kube\config"
$env:KUBECONFIG = $kubeconfig

$bootstrapArguments = @(
  "-chdir=infra"
  "apply"
  "-auto-approve"
  "-target=kubernetes_namespace_v1.auto_shop"
  "-var-file=terraform.tfvars.example"
  "-var=namespace=$namespace"
  "-var=kubeconfig_path=$kubeconfig"
  "-var=kube_context=kind-kind"
)

terraform @bootstrapArguments
```

Crie o Secret no namespace usando um mecanismo externo. Para um teste local,
credenciais efêmeras podem ser geradas na sessão do PowerShell:

```powershell
$dbPassword = [guid]::NewGuid().ToString("N")
$secretKey = [guid]::NewGuid().ToString("N")

kubectl create secret generic auto-shop-secrets `
  --namespace $namespace `
  --from-literal="DATABASE_URL=postgresql://oficina:$dbPassword@postgres-service:5432/oficina" `
  --from-literal="DB_NAME=oficina" `
  --from-literal="DB_USER=oficina" `
  --from-literal="DB_PASSWORD=$dbPassword" `
  --from-literal="SECRET_KEY=$secretKey" `
  --from-literal="INVERTEXTO_API_TOKEN=local-ci-token" `
  --from-literal="SMTP_USER=" `
  --from-literal="SMTP_PASSWORD="
```

Execute então o apply completo, sem `-target`:

```powershell
$applyArguments = @(
  "-chdir=infra"
  "apply"
  "-auto-approve"
  "-var-file=terraform.tfvars.example"
  "-var=namespace=$namespace"
  "-var=kubeconfig_path=$kubeconfig"
  "-var=kube_context=kind-kind"
  "-var=enable_local_database=true"
)

terraform @applyArguments
```

O `StorageClass` local pode usar `WaitForFirstConsumer`. Por isso, o PVC pode
ficar inicialmente `Pending` até o Deployment PostgreSQL ser criado; isso é
esperado. O Terraform não deve aguardar o PVC antes de criar seu primeiro
consumidor.

Valide o resultado com:

```powershell
kubectl get pods,jobs,pvc,svc,hpa,ingress --namespace $namespace
terraform -chdir=infra plan `
  -var-file terraform.tfvars.example `
  -var "namespace=$namespace" `
  -var "kubeconfig_path=$kubeconfig" `
  -var "kube_context=kind-kind" `
  -var "enable_local_database=true"
```

Após um apply bem-sucedido, o segundo plano deve retornar `No changes`. Em Kind,
os campos de métricas do HPA podem aparecer como `unknown` se o Metrics Server
não estiver instalado; o recurso ainda estará criado com as metas configuradas.

## Recursos existentes

Se o namespace ou os recursos já existirem, importe-os para o state antes do
primeiro apply. O Job de migration é versionado pela imagem e normalmente deve
ser criado pelo Terraform na primeira execução. O Job não possui TTL automático:
isso evita que o Kubernetes o remova enquanto ele ainda está registrado no state.
Jobs antigos podem ser limpos manualmente somente depois de confirmar que não
estão associados ao state ativo.

```bash
terraform -chdir=infra import kubernetes_namespace_v1.auto_shop auto-shop
terraform -chdir=infra import kubernetes_config_map_v1.app auto-shop/auto-shop-config
terraform -chdir=infra import kubernetes_job_v1.migration auto-shop/auto-shop-migrate-<hash-da-imagem>
terraform -chdir=infra import kubernetes_deployment_v1.backend auto-shop/auto-shop-backend
terraform -chdir=infra import kubernetes_service_v1.backend auto-shop/auto-shop-backend-service
terraform -chdir=infra import kubernetes_horizontal_pod_autoscaler_v2.backend auto-shop/auto-shop-backend-hpa
terraform -chdir=infra import 'kubernetes_ingress_v1.backend[0]' auto-shop/auto-shop-ingress
```

Os IDs devem ser conferidos no cluster antes do import. Não importe recursos
gerenciados por outro state Terraform. O endereço do Job é derivado de
`substr(sha256(image_reference), 0, 12)`; use a mesma referência de imagem que
será configurada no `terraform.tfvars`.

Quando o banco local já existir, importe também os recursos condicionais:

```bash
terraform -chdir=infra import 'kubernetes_persistent_volume_claim_v1.postgres[0]' auto-shop/postgres-pvc
terraform -chdir=infra import 'kubernetes_deployment_v1.postgres[0]' auto-shop/postgres
terraform -chdir=infra import 'kubernetes_service_v1.postgres[0]' auto-shop/postgres-service
```

Use esta sequência para assumir um ambiente atualmente gerenciado pelo
Kustomize:

1. Pare os deploys Kustomize do ambiente e não aplique mais nenhuma fase nesse
   namespace.
2. Configure o Terraform com os mesmos nomes, imagem e valores não sensíveis
   usados pelo ambiente atual.
3. Importe todos os recursos existentes, incluindo os recursos condicionais do
   banco local quando aplicável.
4. Execute `terraform plan` e revise qualquer alteração ou destruição antes do
   primeiro `apply`.
5. Depois da validação, mantenha apenas o Terraform como proprietário daquele
   ambiente.

Em um namespace novo, os imports não são necessários. O Terraform criará os
recursos diretamente, desde que o Secret exigido já exista.

## Banco local

Quando habilitado, `db.tf` cria o PVC `postgres-pvc`, o Deployment `postgres` e
o Service `postgres-service`. As credenciais são lidas pelo Pod diretamente do
Secret Kubernetes existente; elas não passam pelo Terraform state.

O banco local é adequado para Kind/Docker Desktop e desenvolvimento. Staging e
production devem apontar `DATABASE_URL` para um PostgreSQL externo e manter
`enable_local_database = false`.
