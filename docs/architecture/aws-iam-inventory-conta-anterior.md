# Inventário IAM da conta AWS anterior

- **Data da leitura:** 2026-10-25
- **Conta consultada:** `Oficina Workload - 16SOAT` (`837155819003`)
- **Escopo:** leitura de IAM, AWS Organizations, IAM Identity Center e comparação com os módulos Terraform locais.
- **Segurança:** nenhum segredo, senha, chave de acesso, código MFA, e-mail ou nome de usuário individual foi coletado para este documento. A conta não foi alterada.

Este inventário serve como referência para planejar uma conta nova. Ele não é uma instrução para copiar as permissões existentes literalmente. O usuário confirmou que o participante que saiu do grupo ainda controla o usuário raiz, os meios de recuperação e a conta de gerenciamento/faturamento; portanto, a conta consultada não será usada pela Fase 3 enquanto isso persistir.

## Estrutura da conta e do IAM

| Área | Estado observado |
| --- | --- |
| AWS Organizations | A conta consultada é a conta de gerenciamento de uma organização com recursos habilitados (`ALL`). A organização contém somente esta conta; não há conta de workload separada. |
| IAM users/groups locais | Nenhum usuário IAM e nenhum grupo IAM. O acesso humano é federado pelo IAM Identity Center. |
| IAM roles | Nove no total: três `AWSReservedSSO_*` geradas pelo Identity Center e seis service-linked roles gerenciadas pela AWS. Nenhuma role de workload/deploy própria foi encontrada. |
| Policies IAM locais | Uma policy própria, `WorkloadBoundary`; não está anexada a principals e tem zero usos como permissions boundary. |
| OIDC providers IAM | Nenhum. GitHub Actions ainda não tem trust OIDC provisionado nesta conta. |
| SAML providers IAM | Um provider `AWSSSO_*_DO_NOT_DELETE`, gerenciado pelo IAM Identity Center. Não recriar manualmente. |
| Política de senha IAM | Não configurada; não há IAM users locais. Isso não representa a política de senha do Identity Center, que é separada. |
| MFA do usuário raiz | O resumo da conta indica MFA habilitado. O dispositivo/segredo MFA pertence ao usuário raiz atual e não deve ser migrado ou copiado. |
| Aliases da conta | Nenhum alias IAM configurado. |

O IAM Identity Center tem uma instância de organização ativa, propriedade da conta de gerenciamento, com região primária `sa-east-1` e réplica em `us-west-2`. Há cinco usuários e quatro grupos: `devops`, `admin-plataforma`, `suporte` e `devops-externo`. Os IDs de identidade são locais ao identity store antigo e não são reutilizáveis na nova conta.

As contagens atuais são: `devops` (3 membros), `admin-plataforma` (3), `suporte` (1) e `devops-externo` (1). Os grupos podem conter pessoas em comum; os membros individuais não são listados aqui.

## Permission sets e atribuições observadas

As atribuições abaixo incluem grupos e usuários individuais. Para a conta nova, devem ser recriados somente os membros atuais e a associação por grupo; não importar identidades antigas nem preservar automaticamente atribuições individuais.

| Permission set | Sessão | Permissões observadas | Atribuições observadas | Recomendação para a nova conta |
| --- | --- | --- | --- | --- |
| `AdminPlataforma` | 4 horas | Managed policy `AdministratorAccess`. | Grupos `devops` e `admin-plataforma`, mais três usuários individuais. | Recriar acesso administrativo apenas para um grupo pequeno de mantenedores ativos. Não atribuir `AdministratorAccess` a todo `devops`. |
| `DevOpsInfra` | 8 horas | Policy inline sem managed policies. Permite operações amplas em S3, EKS, RDS, Lambda, Secrets Manager, EC2, ELB, Auto Scaling, CloudWatch Logs/metrics e ECR, em grande parte com `Resource: "*"`. Inclui negação fora de `us-east-1`, limites para alguns tipos de instância/RDS e guardrails para operações IAM, Organizations, CloudTrail e buckets críticos. | Grupos `devops` e `admin-plataforma`, mais quatro usuários individuais. | Não copiar o JSON atual. Gerar permissões a partir dos repositórios/stacks e limitar recursos, ações, região e `iam:PassRole`; manter roles humanas separadas de roles de workload. |
| `SuporteContratos` | 8 horas | Policy inline `s3:ListBucket`, `s3:GetBucketLocation` e `s3:GetObject`, limitada ao bucket `oficina-contratos-837155819003`. | Um usuário individual; o grupo `suporte` não está atribuído. | Não recriar por padrão. Só criar acesso de leitura se houver dados de contratos na conta nova; limitar ao bucket novo e ao grupo de usuários atual que realmente precisa dele. |

**Risco identificado:** o grupo `devops` recebe o permission set `AdminPlataforma`, que contém `AdministratorAccess`. A cópia dessa atribuição daria administração total a todo o grupo. A nova configuração deve corrigir isso e privilegiar atribuições a grupos menores, com papéis distintos para administração e operação.

Na policy `DevOpsInfra`, alguns controles mais específicos incluem leitura de IAM, criação/alteração de roles `workload-*` com `WorkloadBoundary`, `iam:PassRole` limitado a essas roles e serviços listados, operações KMS condicionadas a tags `Project=oficina`, negações de criação de IAM users/access keys, controle de Organizations, desligamento de CloudTrail e alteração da boundary, além de limites de tipos EC2/RDS. Esses controles são referências de intenção, não uma policy pronta para a conta nova.

O grupo `suporte` e o grupo `devops-externo` existem no identity store antigo, mas não aparecem nas atribuições dos três permission sets observados. Não conceder acesso na conta nova apenas por terem existido.

## Policy `WorkloadBoundary`

A policy local `WorkloadBoundary` tem `AttachmentCount = 0` e `PermissionsBoundaryUsageCount = 0`; não limita nenhum principal atual. O permission set `DevOpsInfra` permite operações IAM específicas em roles `workload-*` quando a criação/alteração recebe essa boundary, mas não há roles de workload com essa boundary na conta.

A boundary contém permissões amplas com `Resource: "*"` para S3, Secrets Manager, KMS, RDS IAM auth, Lambda, CloudWatch, EC2, ELB, Auto Scaling, EKS/EKS Pod Identity e ECR; nega pedidos fora de `us-east-1`, escrita/exclusão em buckets `oficina-tfstate*`, e restringe algumas ações. Não adotá-la sem revisão: uma permissions boundary limita o máximo permitido a um principal, mas esta versão é ampla e está vinculada a nomes e serviços específicos da conta anterior.

## Comparação com os repositórios

As roles encontradas nos arquivos Terraform são definições versionadas; elas não foram encontradas provisionadas na conta consultada.

| Código | Papel/uso | Observação para a migração |
| --- | --- | --- |
| `auto-shop-system/infra/aws/lambda.tf` | Uma role de execução é compartilhada por `auth_login` e `jwt_authorizer`, com `AWSLambdaBasicExecutionRole`. | Reavaliar a separação por função e as permissões runtime antes de aplicar; Terraform deve criar os papéis. |
| `auto-shop-system/infra/aws/logging.tf` | Role de API Gateway para CloudWatch; a policy permite várias ações `logs:*` em `Resource: "*"`. | Escopar para grupos/log streams de log necessários, se esse módulo continuar sendo usado na arquitetura aprovada. |
| `pos/lambda-auth/infra/terraform/main.tf` | Role de execução própria para Lambda. Lê um segredo específico, usa chave KMS específica e escreve no log group; ações ENI usam `Resource: "*"` quando a Lambda entra na VPC. | Recriar pelo módulo Terraform, fornecendo os ARNs da conta nova e revisar permissões ENI conforme a orientação da AWS. |
| Workflows de CI/CD dos dois repositórios | A busca local não encontrou configuração de `configure-aws-credentials`, `role-to-assume` ou trust OIDC do GitHub. | Criar provider OIDC e roles de CI na conta nova, restritos ao repositório, branch e GitHub Environment autorizados; sem access keys estáticas. |

O deploy de infraestrutura também precisará dos papéis da plataforma que ainda serão definidos em `k8s-infra`/`database-infra`, além das identidades de runtime, migration, ESO, Lambda e runner descritas no ADR-0071. Esses papéis não são substituídos pelos permission sets humanos acima.

## Plano de reprodução seguro

1. Criar uma conta AWS standalone sob controle dos membros ativos. Não criar a nova conta como membro da organização administrada pelo ex-participante.
2. Definir e-mail raiz de grupo exclusivo, contato/telefone de recuperação durável e MFA com processo documentado de recuperação. A conta e o método de pagamento precisam ter um responsável ativo definido.
3. A escolha standalone foi aprovada para o único staging desta fase. Não recriar a instância antiga do IAM Identity Center: em conta standalone ela não fornece o portal SSO para acesso a contas AWS.
4. Criar uma identidade IAM individual por mantenedor ativo, com login próprio no console, MFA obrigatório e sem access keys. Não compartilhar credenciais humanas, importar o roster antigo ou reutilizar IDs, sessões ou MFA da instância anterior.
5. Separar o acesso humano operacional das roles de workload/deploy. Restringir administração total ao menor grupo ativo possível; usar roles temporárias e permissões específicas para Terraform, limitadas à região `us-east-1`, repositórios, serviços e `iam:PassRole` necessários. Não atribuir `AdministratorAccess` ao grupo geral `devops`.
6. Para desenvolvimento local com AWS CLI, usar `aws login` com console credentials e perfil `oficina-workload`, recebendo credenciais temporárias; exigir a policy `SignInLocalDevelopmentAccess` conforme a AWS. Não criar credenciais permanentes para a CLI.
7. Derivar as policies operacionais dos stacks Terraform, usando ARNs da nova conta, privilégios mínimos e condições de trust adequadas. Revisar `WorkloadBoundary` antes de decidir se uma nova boundary será necessária.
8. Criar OIDC para GitHub e as roles de CI/CD quando houver repository/branch/environment finais. Recriar as roles de serviços pelos respectivos Terraform, não manualmente.
9. Conferir o plano e a elegibilidade Free Tier da nova conta. A AWS limita plano/créditos a novos clientes e não transfere créditos entre contas; não assumir que uma conta nova do grupo receberá créditos.

## Referências AWS

- [Roles criadas pelo IAM Identity Center](https://docs.aws.amazon.com/singlesignon/latest/userguide/identity-center-and-iam-roles.html)
- [Instâncias organizacionais e standalone do IAM Identity Center](https://docs.aws.amazon.com/singlesignon/latest/userguide/identity-center-instances.html)
- [Práticas para a conta de gerenciamento da AWS Organizations](https://docs.aws.amazon.com/organizations/latest/userguide/orgs_best-practices_mgmt-acct.html)
- [Criar uma conta membro na AWS Organizations](https://docs.aws.amazon.com/organizations/latest/userguide/orgs_manage_accounts_create.html)
- [Práticas para ambiente multi-account](https://docs.aws.amazon.com/organizations/latest/userguide/orgs_best-practices.html)
- [AWS Free Tier: elegibilidade e créditos](https://aws.amazon.com/free/free-tier-faqs/)
