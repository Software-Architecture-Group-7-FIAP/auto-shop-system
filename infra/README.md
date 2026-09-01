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

1. Instale Terraform 1.6 ou superior e configure um kubeconfig com acesso ao
   cluster desejado.
2. Copie `terraform.tfvars.example` para `terraform.tfvars` e ajuste apenas os
   valores não sensíveis do ambiente.
3. Crie `auto-shop-secrets` por um mecanismo externo e seguro. Nunca coloque
   credenciais no arquivo `.tfvars` versionado.

O provider usa `kubeconfig_path` e `kube_context` quando informados; quando
omitidos, usa a configuração padrão do Kubernetes. O arquivo de state local,
planfiles e tfvars reais são ignorados pelo Git.

## Comandos

```bash
terraform -chdir=infra init -backend=false
terraform -chdir=infra fmt -check -recursive
terraform -chdir=infra validate
terraform -chdir=infra plan -var-file=terraform.tfvars
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

## Recursos existentes

Se o namespace ou os recursos já existirem, importe-os para o state antes do
primeiro apply. O Job de migration é versionado pela imagem e normalmente deve
ser criado pelo Terraform na primeira execução.

```bash
terraform -chdir=infra import kubernetes_namespace_v1.auto_shop auto-shop
terraform -chdir=infra import kubernetes_config_map_v1.app auto-shop/auto-shop-config
terraform -chdir=infra import kubernetes_deployment_v1.backend auto-shop/auto-shop-backend
terraform -chdir=infra import kubernetes_service_v1.backend auto-shop/auto-shop-backend-service
```

Os IDs devem ser conferidos no cluster antes do import. Não importe recursos
gerenciados por outro state Terraform.

## Banco local

Quando habilitado, `db.tf` cria o PVC `postgres-pvc`, o Deployment `postgres` e
o Service `postgres-service`. As credenciais são lidas pelo Pod diretamente do
Secret Kubernetes existente; elas não passam pelo Terraform state.

O banco local é adequado para Kind/Docker Desktop e desenvolvimento. Staging e
production devem apontar `DATABASE_URL` para um PostgreSQL externo e manter
`enable_local_database = false`.
