# ADR-0079: Espelhar imagens de GHCR para ECR privado

- Status: aceita
- Data: 2026-11-01
- Supersedes: estratégia de distribuição de imagens da ADR-0074

## Contexto

O deploy falhou antes de autenticar na AWS: o runner tentou fazer pull anônimo de GHCR e recebeu `unauthorized`. Manter a imagem de aplicação publicamente acessível no GHCR não é necessário para que os nós EKS executem a versão implantada.

O repositório ECR `auto-shop-system` já é esperado pelo helper de mirror. A existência, região, imutabilidade atual do repositório e a policy externa de permissions boundary precisam ser verificadas antes da ativação; esta ADR não provisiona nem altera recursos AWS.

## Decisão

- O build continua publicando no GHCR tags baseadas no commit `sha-<7>` com `GITHUB_TOKEN`.
- Apenas o deploy autorizado por `workflow_dispatch`, na branch e GitHub Environment correspondentes, pode iniciar a cópia. Ele precisa passar pela autorização de lifecycle e obter credenciais AWS por OIDC.
- Depois de OIDC, o job lê GHCR com `GITHUB_TOKEN` e `packages: read`. O helper só aceita a imagem deste repositório e do commit atual, valida o rótulo OCI de revisão e exige que a tag de destino ECR seja imutável.
- O helper espelha e valida a imagem no ECR privado `auto-shop-system`; a referência ECR retornada segue para `k8s/scripts/deploy.sh`.
- As roles de deploy `staging` e `production` recebem permissões de push e pull limitadas ao ARN desse repositório ECR. `ecr:GetAuthorizationToken` permanece na policy com `Resource: "*"`, conforme o requisito do serviço.
- EKS obtém imagens do ECR. A role dos nós (ou a role de execução do Fargate) deve ter as permissões de pull e acesso de rede ao ECR e S3. Não se adicionam credenciais estáticas nem `imagePullSecret` ao cluster.

## Consequências e pré-requisitos

- A imagem publicada no GHCR não precisa ser pública; o package precisa conceder acesso de leitura ao `GITHUB_TOKEN` do repositório para o job de deploy.
- A permissions boundary `auto-shop/auto-shop-boundary` é externa ao checkout. Ela precisa permitir as ações ECR concedidas pela policy da role, caso contrário a avaliação efetiva continuará negando a operação.
- O repositório ECR deve existir na conta e região usadas pelo deploy e ter image tag mutability `IMMUTABLE`. O helper falha fechado se qualquer condição não coincidir.
- A role dos nós EKS precisa permitir `ecr:GetAuthorizationToken`, `ecr:BatchGetImage`, `ecr:BatchCheckLayerAvailability` e `ecr:GetDownloadUrlForLayer`; nodes também precisam de conectividade à API ECR, ao Docker registry ECR e ao S3.
- A role OIDC da aplicação ganha permissão de escrita no repositório da imagem. A policy é restrita ao nome `auto-shop-system`, e o deploy continua condicionado à autorização de lifecycle, ao environment e à branch correta.

## Verificação

Os contratos e testes unitários validam a referência GHCR recebida, a associação ao commit atual, a imutabilidade do destino ECR, a ausência de pull anônimo no workflow, as permissões ECR da role, e a passagem da referência ECR ao script de deploy. Nenhum setting de GitHub/AWS, deploy ou apply foi executado por esta mudança.
