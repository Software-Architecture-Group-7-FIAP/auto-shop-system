# Operação por ambiente

Os manifests Kubernetes são separados por ambiente e por fase:

```text
k8s/
  base/{foundation,migration,app,ingress}/
  overlays/{local,staging,production}/{foundation,migration,app,ingress}/
  examples/secrets.example.env
```

Não existe um agregador que aplique migration e API juntos. A ordem de
execução é sempre `foundation`, `migration`, `app` e, quando necessário,
`ingress`.

## Local

1. Copie `k8s/examples/secrets.example.env` para
   `k8s/overlays/local/secrets.env` e substitua todos os placeholders. O
   arquivo de destino é ignorado pelo Git; `DATABASE_URL` é gerada a partir de
   `DB_NAME`, `DB_USER` e `DB_PASSWORD`.
2. Confirme o contexto do Kind ou Docker Desktop com `kubectl config current-context`.
3. Execute `./k8s/scripts/deploy.ps1 -Environment local` no PowerShell.

O overlay local cria PostgreSQL com uma réplica e probes `pg_isready`, além do
MailHog. O script constrói uma referência local única por execução e a carrega
explicitamente no Kind quando disponível; o pipeline de CI faz o mesmo para
`auto-shop-system:local`.

Para o Compose, copie `.env.example` para `.env` e substitua os placeholders.
Suba primeiro somente as dependências, construa a imagem, execute a migration
explicitamente e só então inicie a API:

```bash
docker compose up db mailhog -d
docker compose build api
docker compose run --rm api alembic upgrade head
docker compose up api
```

## Staging e production

Staging e production não criam banco, Secret ou certificado. Antes do deploy,
provisione no namespace `auto-shop`:

- `auto-shop-secrets` com `DATABASE_URL`, `SECRET_KEY`,
  `INVERTEXTO_API_TOKEN`, `SMTP_USER` e `SMTP_PASSWORD`;
- `staging-auto-shop-tls` ou `auto-shop-tls` com o certificado correspondente.

Use uma referência de imagem imutável, preferencialmente digest:

```powershell
./k8s/scripts/deploy.ps1 -Environment staging `
  -ImageReference ghcr.io/example/auto-shop-system:0123456789abcdef0123456789abcdef01234567
./k8s/scripts/deploy.ps1 -Environment production `
  -ImageReference ghcr.io/example/auto-shop-system@sha256:<64-hex-digest> `
  -ConfirmProduction
```

O script valida as ferramentas, contexto, Secret sem exibir valores, lock por
ambiente, Kustomize, readiness do banco, conclusão da migration, rollout da API
e os endpoints `/health/live`, `/health/ready` e `/docs`. Cada referência de
release recebe um Job de migration próprio; Jobs ativos nunca são removidos por
um deploy posterior. Falhas preservam o código de saída e nunca imprimem a
connection string.

Produção e staging usam HTTPS, HSTS e redirect de HTTP para HTTPS. O Secret TLS
deve ser emitido por cert-manager ou provisionado por um processo externo; o
script não cria certificados automaticamente.

## Terraform (alternativa declarativa)

O diretório [`infra/`](../infra/README.md) oferece uma alternativa ao Kustomize
para gerenciar Namespace, ConfigMap, migration, backend, Service, HPA e Ingress
em um cluster Kubernetes existente. Ele não provisiona AWS, EKS, VPC, IAM, RDS
ou PostgreSQL externo.

Use Terraform ou Kustomize por ambiente, nunca os dois simultaneamente no mesmo
namespace. O Kustomize continua disponível para compatibilidade e para o fluxo
operacional documentado acima; quando Terraform for escolhido, ele passa a ser
o proprietário declarado dos recursos daquele ambiente.

No Terraform:

- o Secret `auto-shop-secrets` é criado previamente por um mecanismo externo e
  nunca é armazenado no state;
- `enable_local_database=true` é permitido somente em `local`;
- staging e production usam PostgreSQL externo e devem manter
  `enable_local_database=false`;
- a imagem da API deve usar digest ou tag baseada em SHA;
- o Job de migration é versionado pela imagem, aguarda conclusão antes do
  Deployment e não possui TTL automático para não desaparecer do state.

O passo a passo, incluindo imports para assumir um namespace já gerenciado pelo
Kustomize e comandos específicos do PowerShell, está em
[`infra/README.md`](../infra/README.md).

## Rollback e diagnóstico

Para rollback, aponte `-ImageReference` para um digest ou tag SHA de uma release
anterior e repita o fluxo. Não execute Alembic dentro das réplicas da API.

Em falha de migration, consulte apenas os logs do Job após remover/mascarar
qualquer credencial. O código de saída `10` indica que o banco não ficou
disponível no preflight; `20` indica falha da migration. Uma migration falha
bloqueia a aplicação da fase `app`.
