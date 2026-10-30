# Operação por ambiente

Os manifests Kustomize são organizados por ambiente e fase:

```text
k8s/
  base/{foundation,migration,app,ingress}/
  overlays/{local,staging,production}/{foundation,migration,app,ingress}/
```

No ambiente local, a ordem é `foundation`, `migration`, `app` e `ingress`. Nos deploys AWS, o script aplica `foundation`, `migration` e `app`; o NGINX Ingress é somente local. Na AWS, o caminho público passa pelo API Gateway e VPC Link até o ALB interno gerenciado por `k8s-infra`.

## Local

1. Copie `k8s/examples/secrets.example.env` para `k8s/overlays/local/secrets.env` e substitua os placeholders. O arquivo de destino é ignorado pelo Git; não publique valores secretos.
2. Confirme o contexto Kind ou Docker Desktop com `kubectl config current-context`.
3. Execute `./k8s/scripts/deploy.ps1 -Environment local` no PowerShell.

O overlay local cria PostgreSQL e MailHog. Para Docker Compose, copie `.env.example` para `.env`, suba as dependências, aplique as migrations e inicie a API:

```bash
docker compose up db mailhog -d
docker compose build api
docker compose run --rm api alembic upgrade head
docker compose up api
```

## AWS: `hml` e `prd`

O Angular chama a API por caminhos relativos `/api/v1/...`. Mantenha as chamadas no mesmo dominio do frontend: cada distribuicao CloudFront encaminha `api/*` para o API Gateway com o prefixo de stage (`/hml` ou `/prd`). Isso preserva o escopo dos cookies de sessao e do CSRF; nao configure no bundle uma URL absoluta para `api.oficina-workshop.com.br`.

Quando `hml` estiver implantado e os dominios estiverem ativos, valide manualmente em `https://app-hml.oficina-workshop.com.br`:

1. Faca login e confirme no Network que `POST /api/v1/auth/login` usa o dominio `app-hml` e retorna sucesso.
2. Confirme que `oficina_access` e `oficina_refresh` sao cookies `HttpOnly` com `Path` restrito a `/api/v1/admin` e `/api/v1/auth`; `oficina_csrf` deve estar disponivel para o interceptor.
3. Recarregue a pagina autenticada e confirme que `GET /api/v1/admin/me` retorna o usuario atual.
4. Abra uma tela administrativa que leia dados e confirme que as respostas chegam pelo mesmo dominio do frontend.
5. Faca logout e confirme que a tela protegida exige novo login.

Repita os passos em `https://app.oficina-workshop.com.br` apos ativar `prd`. O bundle e o mesmo nos dois ambientes; o dominio CloudFront seleciona a origem `/hml` ou `/prd`.

Existe uma única infraestrutura AWS efêmera `staging`; dentro dela, `hml` e `prd` usam os namespaces `auto-shop-hml` e `auto-shop-prd`, bancos lógicos e stages API Gateway separados. `production` é o GitHub Environment do deploy lógico `prd`, não uma segunda conta, cluster ou RDS. Consulte a [ADR-0071](architecture/decisions/ADR-0071-infraestrutura-cloud-fase-3.md) para o contrato vigente.

O pipeline atual funciona assim:

| Origem | GitHub Environment | Namespace | Stage API | Frontend |
|---|---|---|---|---|
| Push em `develop` | `staging` | `auto-shop-hml` | `hml` | `app-hml.oficina-workshop.com.br` |
| Push em `main` | `production` | `auto-shop-prd` | `prd` | `app.oficina-workshop.com.br` |

Os workflows publicam a imagem do backend no GHCR. O deploy só roda quando `DEPLOY_STAGING_ENABLED` ou `DEPLOY_PRODUCTION_ENABLED` está ligado no repositório. O frontend é publicado depois que o backend do mesmo ambiente termina com sucesso. Mantenha os gates desligados até a infraestrutura, os GitHub Environments e os smoke checks necessários estarem prontos. O fluxo `session-up`/`session-down` e o teardown agendado pedidos pela issue #87 ainda não estão implementados neste repositório.

Antes do deploy, o ambiente precisa existir e publicar os parâmetros SSM documentados em [`infra/aws/README.md`](../infra/aws/README.md). O secret `auto-shop-secrets` é fornecido pelo mecanismo externo aprovado; nunca passe seu conteúdo por Terraform, logs ou artefatos. O job de CI busca do SSM o nome do cluster e os destinos S3/CloudFront. A role OIDC precisa do acesso ao namespace correspondente configurado no EKS.

O script `k8s/scripts/deploy.sh` cria o namespace, verifica as chaves do segredo de runtime sem imprimir valores, aplica foundation e migration, aguarda a migration, atualiza a API e executa smoke checks privados por `kubectl port-forward`. O smoke local cobre saude e documentacao privada, mas nao substitui o fluxo de negocio, HPA ou teardown da issue #87. O Job usa o ServiceAccount `auto-shop-migration` e uma role EKS Pod Identity por namespace, definidas em `infra/aws`. O deploy de staging le `/database/secrets/migrations-hml-arn`; o deploy de producao le `/database/secrets/migrations-prd-arn`. Cada role anexa somente a policy de leitura do segredo de migration do proprio database. O processo monta a conexao em memoria com `sslmode=verify-full` e o bundle CA RDS incluido na imagem. O segredo `owner` fica reservado ao bootstrap e nao e sincronizado ao Kubernetes.

O ConfigMap define `API_ROOT_PATH` como `/hml` ou `/prd`. O cliente valida JWT RS256 via JWKS publicado pela Lambda de autenticacao. O issuer, audience, CORS, URLs e as rotas publicas precisam permanecer coerentes entre a API, a Lambda e os dois frontends. `/docs`, `/redoc` e `/openapi.json` nao sao publicados pelo API Gateway. A API Gateway envia OPTIONS do token de cliente a Lambda e as rotas de sessao ao middleware CORS do backend.

Ainda faltam a publicação do ARN da Lambda no SSM pela stack `lambda-auth`, a coordenação da sessão entre repositórios upstream, os fluxos de negócio em `hml` e `prd`, evidência de HPA no EKS e teardown sem órfãos. O smoke local em Kind valida manifests e comportamento local; não substitui essas evidências. A issue #87 permanece aberta.

## Domínio e ativação

O código Terraform mantém `enable_custom_domains = false` até que os CNAMEs de validação ACM estejam publicados no Registro.br. Depois da validação do certificado, o plano deve incluir o domínio `api.oficina-workshop.com.br`, base paths `hml`/`prd` e aliases CloudFront dos dois frontends. Faça os smoke checks públicos nos dois stages e só então avalie desabilitar o endpoint `execute-api` em um plano separado.

Não existe autorização implícita para `terraform apply` ou deploy. Antes de qualquer sessão AWS, confira custo, região, conta, recursos e teardown conforme o ADR-0064; cada apply exige validação específica. O custo por sessão ainda precisa incluir CloudFront/S3, WAFs, ACM/domínio e o ciclo completo de criação e destruição.

## Registry visibility decision

The GHCR package remains private. Authorized deployment jobs read the immutable `sha-<commit>` image with a read-only `GITHUB_TOKEN`, verify its source revision, and mirror it to the private ECR repository `auto-shop-system` with the GitHub OIDC deployment role. The EKS nodes pull the ECR image through their AWS identity; no long-lived GHCR token or Kubernetes `imagePullSecret` is needed. The private ECR lifecycle policy retains the ten most recent SHA-tagged images.

## Terraform local

O diretório [`infra/`](../infra/README.md) é uma alternativa declarativa para recursos Kubernetes em um cluster existente. Não provisiona a AWS. Use Terraform ou Kustomize para um ambiente, nunca os dois ao mesmo tempo no mesmo namespace. A stack da borda AWS é separada em [`infra/aws/`](../infra/aws/README.md).

## Rollback e diagnóstico

Para rollback do backend, publique uma release anterior por digest ou tag baseada em SHA e repita o deploy após validar a compatibilidade das migrations. O rollback da aplicação não reverte migrations; mantenha-as compatíveis com as duas versões durante a transição.

Em falha de migration, consulte somente os logs sanitizados do Job. A falha interrompe o deploy antes do rollout da API. Não copie connection strings nem tokens para issues, comentários ou logs.
