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

Existe uma única infraestrutura AWS efêmera `staging`; dentro dela, `hml` e `prd` usam os namespaces `auto-shop-hml` e `auto-shop-prd`, bancos lógicos e stages API Gateway separados. `prd` é o GitHub Environment do deploy lógico `prd`, não uma segunda conta, cluster ou RDS. Consulte a [ADR-0071](architecture/decisions/ADR-0071-infraestrutura-cloud-fase-3.md) para o contrato vigente.

O pipeline atual funciona assim:

| Origem | GitHub Environment | Namespace | Stage API | Frontend |
|---|---|---|---|---|
| `workflow_dispatch` em `develop` | `hml` | `auto-shop-hml` | `hml` | `app-hml.oficina-workshop.com.br` |
| `workflow_dispatch` em `main` | `prd` | `auto-shop-prd` | `prd` | `app.oficina-workshop.com.br` |

As mudanças de produto entram por pull requests de branches de trabalho para `develop`. A passagem para `main` é feita por um único pull request de release com `develop` como origem; não abra pull requests de feature diretamente para `main`.

Os pushes publicam a imagem do backend no GHCR, sem alterar ambientes. O deploy do backend só roda por `workflow_dispatch` com sessão validada e quando `DEPLOY_STAGING_ENABLED` ou `DEPLOY_PRODUCTION_ENABLED` está ligado no repositório. O deploy do frontend exige também o gate separado `DEPLOY_STAGING_FRONTEND_ENABLED` ou `DEPLOY_PRODUCTION_FRONTEND_ENABLED`; mantenha esses gates ausentes ou `false` até a publicação do frontend ser autorizada. Habilitar o deploy do backend não publica o frontend. Mantenha os gates do backend desligados até a infraestrutura, os GitHub Environments e os smoke checks necessários estarem prontos. Os workflows coordenados de abertura, health check, fechamento e contingência de HML estão implementados.

Depois que a mudança for promovida à branch padrão (atualmente `main`) pelo PR de release, `environment-hml-cleanup.yml` poderá rodar diariamente às 02:00 UTC como contingência para sessões HML expiradas. O GitHub só executa gatilhos `schedule` e `workflow_dispatch` quando o arquivo do workflow existe na branch padrão. O workflow de contingência despacha `environment-stop.yml` em `develop`; esse arquivo também precisa existir na branch padrão para que o dispatch funcione, e a versão executada será a da ref `develop`. A regra externa do GitHub Environment `operations` deve permitir a branch padrão para a contingência e `develop` para os jobs de parada.

Dispatches manuais da contingência exigem que o ator esteja listado na variável de repositório ou de Environment `HML_CLEANUP_TRUSTED_OPERATORS`, como logins separados por vírgula. Sem a variável, somente o gatilho agendado é aceito. Mantenha também os revisores e as regras de branches do Environment `operations` restritos a operadores autorizados.

A descoberta seleciona uma única abertura HML e exige que o run de `apply.yml` da infraestrutura, com título correlacionado à sessão, tenha sido aceito e encerrado; o job `apply reviewed saved plan` e o passo `Verify and apply the exact saved plan` também precisam ter começado. Runs upstream ainda ativos ou sem evidência suficiente bloqueiam o fallback. Uma tentativa anterior de fechamento só pode ser repetida se o registro do job `close` provar que todos os passos potencialmente mutáveis ainda não começaram. Se qualquer fase de fechamento começou, ou a evidência estiver ausente ou ambígua, a automação falha e exige revisão manual das fases antes de qualquer nova tentativa. Um fechamento ativo bloqueia em erro visível. Após a autorização, a contingência envia uma capability HML assinada especificamente para emergência e vinculada ao pedido de fechamento; o workflow `environment-stop.yml` aplica o teardown coordenado com prazo emergencial de 40 minutos e reserva 15 minutos para auditoria. A contingência não adquire o grupo de concorrência `environment-lifecycle`, pois o workflow de parada é responsável por esse bloqueio e a contingência aguarda sua conclusão.

Antes do deploy, o ambiente precisa existir e publicar os parâmetros SSM documentados em [`infra/aws/README.md`](../infra/aws/README.md). O secret `auto-shop-secrets` é fornecido pelo mecanismo externo aprovado; nunca passe seu conteúdo por Terraform, logs ou artefatos. O job de backend lê do SSM o cluster e os parâmetros de migrations/EventBridge; o job de frontend lê separadamente os destinos S3/CloudFront. As roles OIDC são distintas: a role de backend recebe acesso ao namespace correspondente no EKS, sem permissão de publicação do frontend.

O script `k8s/scripts/deploy.sh` cria o namespace, valida as chaves do segredo de runtime sem imprimir valores e cria `auto-shop-redis-credentials` uma vez por namespace com senha aleatória. Os arquivos temporários são removidos ao final do job; a senha e a URL ficam somente no Secret Kubernetes. Redis usa armazenamento em memória, sem persistência, e o NetworkPolicy permite entrada apenas dos Pods da API. O script aplica foundation e migration, aguarda a migration e o Redis, atualiza a API e executa smoke checks privados por `kubectl port-forward`. O smoke cobre saúde e documentação privada, mas não substitui o fluxo de negócio, HPA ou teardown da issue #87. O Job usa o ServiceAccount `auto-shop-migration` e uma role EKS Pod Identity por namespace; essa role lê o ARN do segredo dedicado de migrations daquele database publicado no SSM e monta a conexão em memória com `sslmode=verify-full` e o bundle CA RDS incluído na imagem. O segredo de migrations não é sincronizado ao Kubernetes.

Para HML, o deploy lê `/database/secrets/migrations-hml-arn`; para PRD, lê `/database/secrets/migrations-prd-arn`. Cada role recebe somente a policy do database correspondente. O segredo `owner` permanece reservado ao bootstrap.

O ConfigMap define `API_ROOT_PATH` como `/hml` ou `/prd`. O cliente valida JWT RS256 via JWKS publicado pela Lambda de autenticacao. O issuer, audience, CORS, URLs e as rotas publicas precisam permanecer coerentes entre a API, a Lambda e os dois frontends. `/docs`, `/redoc` e `/openapi.json` nao sao publicados pelo API Gateway. A API Gateway envia OPTIONS do token de cliente a Lambda e as rotas de sessao ao middleware CORS do backend.

Ainda faltam provisionar os recursos AWS e parâmetros SSM, publicar os registros DNS e validar os certificados ACM, validar o ciclo completo entre os repositórios upstream e executar os fluxos de negócio em HML e PRD. Também faltam evidência do HPA no EKS e comprovação de teardown sem órfãos. A integração de ARN da Lambda por stage está implementada no Terraform, mas os parâmetros ainda não existem na conta. O smoke local em Kind valida manifests e comportamento local; não substitui essas evidências. A issue #87 permanece aberta até que essas evidências sejam registradas.

## Domínio e ativação

O código Terraform mantém `enable_custom_domains = false` até que os CNAMEs de validação ACM estejam publicados no Registro.br. Depois da validação do certificado, o plano deve incluir o domínio `api.oficina-workshop.com.br`, base paths `hml`/`prd` e aliases CloudFront dos dois frontends. Faça os smoke checks públicos nos dois stages e só então avalie desabilitar o endpoint `execute-api` em um plano separado.

Não existe autorização implícita para `terraform apply` ou deploy. Antes de qualquer sessão AWS, confira custo, região, conta, recursos e teardown conforme o ADR-0064; cada apply exige validação específica. O custo por sessão ainda precisa incluir CloudFront/S3, WAFs, ACM/domínio e o ciclo completo de criação e destruição.

## Registry and image delivery

The build publishes a commit-derived `sha-<7>` image to GHCR. A deploy job runs only after `workflow_dispatch`, lifecycle authorization, and AWS OIDC authentication. It uses authenticated GHCR access through the job-scoped `GITHUB_TOKEN` with `packages: read` to pull the exact image for the workflow commit, checks its OCI revision, and mirrors it to the private ECR repository `auto-shop-system` with immutable tags. The helper verifies the existing repository's account, region, URI, and tag mutability, then confirms that the ECR image matches the GHCR source. The same ECR reference is passed to `k8s/scripts/deploy.sh`.

EKS nodes pull the deployed image from private ECR. The node instance role (or Fargate pod execution role) must be allowed `ecr:GetAuthorizationToken`, `ecr:BatchGetImage`, `ecr:BatchCheckLayerAvailability`, and `ecr:GetDownloadUrlForLayer`; the authorization token action requires `Resource: "*"`. Nodes also need network access to the ECR API, ECR Docker registry, and S3 layer storage, through NAT or the required VPC endpoints. No Kubernetes `imagePullSecret` is needed when the node role supplies ECR pull access.

The existing deploy roles receive ECR mirror permissions scoped to the `auto-shop-system` repository ARN, plus the resource-wide authorization-token action. Their permissions boundary is managed outside this repository and must allow these ECR actions. Before enabling a deploy gate, verify that the ECR repository exists in the configured account and region with immutable tags, the GHCR package grants Actions access to `GITHUB_TOKEN`, the external boundary permits the mirror actions, and the EKS node role and network allow private ECR pulls. These external settings were not changed or verified here.

## Terraform local

O diretório [`infra/`](../infra/README.md) é uma alternativa declarativa para recursos Kubernetes em um cluster existente. Não provisiona a AWS. Use Terraform ou Kustomize para um ambiente, nunca os dois ao mesmo tempo no mesmo namespace. A stack da borda AWS é separada em [`infra/aws/`](../infra/aws/README.md).

## Rollback e diagnóstico

Para rollback do backend, publique uma release anterior por digest ou tag baseada em SHA e repita o deploy após validar a compatibilidade das migrations. O rollback da aplicação não reverte migrations; mantenha-as compatíveis com as duas versões durante a transição.

Em falha de migration, consulte somente os logs sanitizados do Job. A falha interrompe o deploy antes do rollout da API. Não copie connection strings nem tokens para issues, comentários ou logs.
