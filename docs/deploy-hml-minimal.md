# Runbook: deploy mínimo de HML

## Fluxo

O workflow [`deploy-hml-minimal.yml`](../.github/workflows/deploy-hml-minimal.yml) é iniciado manualmente em `develop` e usa o GitHub Environment `hml`. A operação padrão `deploy` constrói a imagem do commit selecionado (`github.sha`), publica no GHCR com a tag derivada `sha-<7>` e espelha a mesma revisão para o repositório privado ECR `auto-shop-system`, onde o helper exige a tag imutável. Depois autentica na AWS por OIDC, lê no SSM os contratos de HML, conecta ao EKS e executa [`deploy.sh`](../k8s/scripts/deploy.sh) com o ambiente `staging` e a referência ECR.

O deploy é do backend no namespace Kubernetes `auto-shop-hml`; não implica publicação do frontend. O script aplica, nesta ordem, `foundation`, `migration`, `seed` e `app`.

O workflow deve primeiro ser integrado à branch padrão `main` para que `workflow_dispatch` esteja disponível no GitHub Actions. Ao executar, selecione `develop` como branch de origem. Escolha `deploy` para o deploy normal ou `prepare-newrelic-secret` para preparar o Secret antes do apply da stack `platform`. Este caminho mínimo cobre backend e integração Kubernetes do New Relic. O frontend fica fora: o workflow reutilizável atual de publicação exige autorização do lifecycle, então esta execução não publica o frontend.

## Ordem durante a abertura de HML

Depois que o EKS e o namespace/RBAC `auto-shop-hml` existirem pelo bootstrap autorizado, execute este workflow em `develop` com `operation=prepare-newrelic-secret`. Esse modo não constrói nem publica imagem e não aplica os manifests da aplicação: ele valida a secret `NEW_RELIC_LICENSE_KEY` do Environment `hml`, conecta ao cluster e cria/atualiza a Kubernetes Secret `auto-shop-new-relic` usando um arquivo temporário com permissão restrita. O valor não é enviado a argumentos de processo nem impresso.

Essa operação precisa terminar antes de aplicar a stack `platform` em [k8s-infra/cluster-apply.yml](https://github.com/Software-Architecture-Group-7-FIAP/k8s-infra/blob/main/.github/workflows/cluster-apply.yml). O workflow de infraestrutura confere a Secret e sua chave antes do Terraform/Helm e falha fechado se a chave estiver ausente. Depois aplique `platform` e execute o workflow novamente com `operation=deploy` (padrão). O deploy normal também atualiza a mesma Secret antes de aplicar os manifests do backend.

## Antes de iniciar

Confirme estes itens com quem administra o repositório e a AWS. Configure os nomes e valores nos escopos indicados sem colocar credenciais em arquivos, inputs, issues ou logs.

| Escopo | Pré-requisito |
|---|---|
| GitHub Environment `hml` | Restrinja as branches de deploy a `develop`; o operador precisa de permissão para iniciar/autorizar seu uso. Configure `AWS_REGION` e `AWS_DEPLOY_ROLE_ARN_HML` como variáveis e `NEW_RELIC_LICENSE_KEY` como secret. O workflow exige que `AWS_REGION` seja `us-east-1`. |
| GitHub Actions e GHCR | O build precisa de `contents: read` e `packages: write`; o deploy precisa de `contents: read`, `packages: read` e `id-token: write`. Se o package GHCR for privado, ele deve conceder acesso ao GitHub Actions deste repositório. O operador também precisa ter permissão para usar o Environment e iniciar Actions. |
| AWS OIDC | A role indicada por `AWS_DEPLOY_ROLE_ARN_HML` deve confiar no OIDC deste repositório/Environment e permitir o mirror para ECR, leitura dos parâmetros SSM e acesso ao cluster EKS. O job usa credenciais temporárias; não cadastre access keys AWS no GitHub. |
| AWS e cluster | O repositório ECR `auto-shop-system` deve existir na região configurada e aceitar tags imutáveis. O cluster e os contratos SSM de HML devem existir; os nós precisam conseguir baixar a imagem do ECR. |
| Kubernetes | A role do workflow precisa de acesso ao cluster e o `eks-pod-identity-agent` deve estar pronto. O namespace deve ter o Secret de runtime `auto-shop-secrets` com as chaves esperadas pelo script. O Job de migration precisa da role Pod Identity e do segredo de banco já provisionados. |

O workflow lê o prefixo `/auto-shop/staging` e espera os parâmetros `/eks/cluster-name`, `/database/secrets/migrations-hml-arn`, `/events/service-order-bus-name` e `/events/service-order-publisher-role-arn/hml`. Os nomes incluem o prefixo completo, por exemplo `/auto-shop/staging/eks/cluster-name`. O runner recebe o ARN do segredo de migration, não o seu conteúdo.

## Executar e acompanhar

1. Depois da integração do workflow em `main`, abra **Actions**, selecione **Minimal HML Deploy** e escolha **Run workflow** com a branch `develop`. Selecione a operação necessária e confira o commit antes de iniciar. `prepare-newrelic-secret` só prepara a Secret; `deploy` constrói, publica e implanta a imagem daquele SHA. Deploys concorrentes compartilham o grupo `cd-staging-${{ github.ref }}` e não cancelam uma execução em andamento, então uma nova execução pode aguardar na fila. Esse grupo serializa o deploy com o workflow antigo `CD Staging`, mas não com `environment-start`, `environment-stop` ou `lifecycle-cleanup`; não execute essas operações de ciclo de vida ao mesmo tempo que o deploy mínimo.
2. Abra o run (nomeado `HML deploy <SHA>`) e acompanhe as etapas de build, push GHCR, mirror ECR, OIDC, leitura SSM, conexão EKS e deploy. O job final `Report HML deployment result` sempre publica um resumo com commit, referências GHCR/ECR e resultados do guard, build e deploy. O campo `Deployed ECR digest` identifica o artefato implantado sem depender de uma tag. A página também mostra duração, logs e anotações. Não copie valores de secrets para comentários ou relatórios.
3. Considere concluído apenas quando o resumo indicar sucesso em todas as fases e o job de deploy terminar com sucesso, incluindo rollout e smoke test. O guard de branch e o resumo têm limite de 5 minutos cada; o job de deploy e o build reutilizável têm 30 minutos. Dentro do script, os Jobs de migration e seed aguardam até 300 segundos cada, os rollouts de Redis e API até 180 e 300 segundos, e a integração Kubernetes do New Relic aguarda até 10 minutos. O smoke faz até 30 tentativas de health, com intervalo de 1 segundo. Se um timeout ocorrer, use a verificação abaixo: fases anteriores podem já ter sido aplicadas.

O smoke test privado usa `kubectl port-forward` para confirmar `/health/live`, `/health/ready` e `/docs`. A readiness probe da API consulta `/health/ready`. Esse smoke confirma a inicialização técnica do backend, não o fluxo funcional da oficina nem o frontend.

## Reintroduzir os gates de CI

Em PRs com destino a `develop`, `metadata` e `manifests` permanecem bloqueantes; a suíte longa, os testes de gateway, os checks Terraform, o smoke de cluster e o frontend ficam temporariamente pulados. Depois de três deploys HML comprovadamente saudáveis, remova essas condições temporárias de `.github/workflows/ci.yml` em etapas, começando por testes e segurança. O push para `develop` continua executando todos esses jobs durante o período temporário.

## Falha parcial e verificação de rollout

`deploy.sh` aplica recursos em fases, não dentro de uma transação. Foundation, migration ou seed podem ter sido aplicados mesmo que uma fase posterior falhe. Uma migration concluída permanece no banco; o script não executa rollback de schema. Se o run falhar ou atingir timeout, registre o run/SHA e a última etapa concluída e verifique o estado do cluster antes de repetir.

Com acesso autorizado ao cluster, confirme o contexto antes dos comandos e confira a imagem realmente configurada no Deployment:

```bash
kubectl config current-context
kubectl -n auto-shop-hml get deployment auto-shop-backend \
  -o=jsonpath='{.spec.template.spec.containers[?(@.name=="backend-api")].image}{"\n"}'
kubectl -n auto-shop-hml rollout history deployment/auto-shop-backend
kubectl -n auto-shop-hml get pods -l app=auto-shop-backend
kubectl -n auto-shop-hml get jobs
```

Compare a imagem do Deployment com o digest ECR registrado no resumo do run. Uma falha antes da aplicação de `app` pode deixar o Deployment na imagem anterior; falha durante ou depois do rollout pode deixar recursos ou Pods parcialmente atualizados. O log de sucesso final do script só é emitido depois do smoke test.

## Reversão manual somente da imagem

Faça reversão apenas se a imagem anterior ainda estiver disponível no ECR e a versão anterior da aplicação for compatível com o schema que já está no banco. Confirme essa compatibilidade com a migration e com a versão anterior antes de agir. Não tente desfazer migration com `kubectl` ou pelo workflow: o deploy não oferece rollback transacional do banco.

Se a análise confirmar compatibilidade, copie a referência ECR por digest de um run anterior bem-sucedido, confirme que o contexto é HML e atualize somente o container `backend-api`:

```bash
kubectl config current-context
kubectl -n auto-shop-hml set image deployment/auto-shop-backend \
  backend-api="${PREVIOUS_ECR_IMAGE_REFERENCE}"
kubectl -n auto-shop-hml rollout status deployment/auto-shop-backend --timeout=300s
kubectl -n auto-shop-hml get deployment auto-shop-backend \
  -o=jsonpath='{.spec.template.spec.containers[?(@.name=="backend-api")].image}{"\n"}'
```

Defina `PREVIOUS_ECR_IMAGE_REFERENCE` com a referência completa por digest publicada no resumo de um deploy anterior (`.../auto-shop-system@sha256:...`). Depois valide readiness e smoke. Se o rollout não ficar pronto, pare e investigue; não reverta schema como tentativa automática de recuperação. O próximo deploy pelo workflow aplicará novamente a imagem do commit escolhido.
