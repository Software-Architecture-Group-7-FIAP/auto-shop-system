# ADR-0071: Arquitetura de infraestrutura cloud da Fase 3

## Atualização vigente — 2026-10-27

Esta atualização prevalece sobre qualquer trecho divergente abaixo; os registros de 2026-10-25 são históricos e não definem o escopo atual.

- **Conta e custo:** a conta `035611741563` agora é **Paid** e recebeu US$ 140 em créditos. O saldo remanescente não foi confirmado nesta revisão. O Cost Explorer exibe US$ 0, sujeito ao atraso de faturamento; `STAGING_ACTIVE=false` e não há EKS, NAT, RDS ou VPC da sessão ativos. Permanecem oito roles IAM. Os budgets de US$ 10, US$ 5 e US$ 1 são alertas, não bloqueios; não existe gatilho configurado de US$ 20. A autorização específica para cada `terraform apply` permanece obrigatória.
- **Quotas:** os limites aprovados são 16 vCPUs On-Demand e 32 Spot. O node group executado na Sessão 1 usa On-Demand; a quota Spot aprovada não altera a decisão de compute sem nova validação de custo e capacidade.
- **Escopo público:** CloudFront/S3 do Angular, domínio próprio e WAF continuam no escopo. A decisão de não reabrir o corte foi confirmada em 2026-10-27. ACM para CloudFront fica em `us-east-1`; o WAF associado ao CloudFront usa escopo `CLOUDFRONT`, separado do WAF `REGIONAL` do API Gateway.
- **Bootstrap do banco:** o desenho aprovado usa init containers `aws-cli` e `postgres:16`, grava arquivos de trabalho, credenciais, payloads e logs temporários em `emptyDir.medium: Memory` (tmpfs) e publica as novas credenciais com `PutSecretValue`. Na criação inicial, `PutSecretValue` associa `AWSCURRENT` automaticamente; em falhas/retries, o Job deve reconciliar PostgreSQL e Secrets Manager e nunca sobrescrever `AWSCURRENT` às cegas. Payloads não podem aparecer em stdout/stderr, argumentos, ConfigMaps ou state Terraform.

## Contratos atuais

- **Ambiente:** uma única infraestrutura AWS `staging`, efêmera e destruída ao final de cada sessão aprovada. Dentro dela, `auto-shop-hml` e `auto-shop-prd`, dois databases lógicos (`autoshop_hml`, `autoshop_prd`) e stages `hml`/`prd`. Não há segunda conta, cluster ou RDS, nem requisitos de alta disponibilidade para produção.
- **Rede e EKS:** VPC dedicada em duas AZs, um NAT Gateway compartilhado, EKS com endpoint público e privado e acesso CI por IAM access entries. Não usar CodeBuild. A aplicação e o RDS não recebem IP público; PostgreSQL aceita apenas os SGs de nodes e Lambda.
- **Banco:** RDS PostgreSQL 16, `db.t4g.micro`, 20 GiB gp3, criptografado e Single-AZ como sizing de staging. Quatro identidades por database: `owner` (master gerenciado pelo RDS, exclusivo do bootstrap), `app_runtime` (DML sem DDL), `migrations` (DDL necessario ao schema) e `lambda_auth` (SELECT somente nas quatro colunas da consulta). ESO sincroniza apenas `app_runtime`; o Job de migrations em `auto-shop-system` le o segredo `migrations` correspondente ao database e usa uma role Pod Identity propria por ambiente, com policy limitada ao ARN exato. `database-infra` mantem a role e a ServiceAccount do bootstrap em `auto-shop-ops`; `k8s-infra` fornece o cluster, o namespace e as politicas de rede. Lambda le seu segredo diretamente. Clientes usam CA oficial e `sslmode=verify-full`.
- **Bootstrap:** Job com init containers `aws-cli` e `postgres:16`, publicação por `PutSecretValue` e volume de trabalho `emptyDir.medium: Memory` com `sizeLimit`. A trust do Pod Identity é restrita ao cluster, namespace e service account. Os containers do mesmo Pod compartilham o role; tratar suas imagens como uma única fronteira de confiança. O fluxo permanece bloqueado até validar a integração `asm-exec` exigida pela política local de secrets.
- **Entrada pública:** API em `api.oficina-workshop.com.br` pelo API Gateway REST Regional, WAF Regional e rate limit 100/5 min em `POST /auth/customer/token`, com 429. A integração VPC Link V2 usa HTTP privado até o ALB interno. Angular em S3 privado + CloudFront/OAC, com `app.oficina-workshop.com.br` e `app-hml.oficina-workshop.com.br`; domínio próprio e ACM continuam no escopo. O WAF do CloudFront tem escopo `CLOUDFRONT`, separado do WAF Regional da API. ACM do CloudFront fica em `us-east-1`.
- **Custo e execução:** conta Paid com US$ 140 em créditos concedidos e saldo não confirmado; budgets de US$ 1/5/10 só alertam. Não há EKS, NAT, RDS ou VPC de sessão ativos; `STAGING_ACTIVE=false`. Recalcular o custo incluindo CloudFront/S3, domínio, ACM, WAFs e teardown. Estado Paid não autoriza `terraform apply` ou deploy; cada sessão exige autorização explícita do ADR-0064.

## Revisão de escopo de 2026-10-25 (histórica; substituída pela atualização vigente)

- **Status:** Aceito para desenho; provisionamento e deploy continuam sujeitos à salvaguarda do ADR-0064.
- **Data:** 2026-10-23
- **Escopo:** Issues de infraestrutura #69–#87 e contratos relacionados de Gateway, CI/CD, observabilidade e planejamento (#68, #90, #92–#95, #98 e #113).
- **Issues relacionadas:** [#69–#87](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/issues?q=is%3Aissue+%2369+OR+%2370+OR+%2371+OR+%2372+OR+%2373+OR+%2374+OR+%2375+OR+%2376+OR+%2377+OR+%2378+OR+%2379+OR+%2380+OR+%2381+OR+%2382+OR+%2383+OR+%2384+OR+%2385+OR+%2386+OR+%2387)

## Contexto

As issues de infraestrutura foram abertas antes da confirmação dos limites entre os repositórios e do caminho público para a API. Os critérios atuais misturam ingress público, API Gateway, permissões de banco e configuração de ambientes. Também há risco de que as trilhas de Terraform compartilhem state com dados sensíveis.

As decisões abaixo fixam a topologia e os limites de segurança para a implementação. Elas não autorizam criar recursos, alterar contas AWS, executar `terraform apply` ou fazer deploy. O ADR-0064 exige aprovação específica de conta, região, ambiente, recursos e custo antes dessas ações.

## Revisão de escopo de 2026-10-25 (histórica; substituída pela atualização vigente)

Revisão feita após a análise de custo e de cobertura do Tech Challenge (`advisor-plans/plano-correcao-fase-3.md`). Entrega da Fase 3: **2026-11-01**. Este registro é histórico; a atualização vigente e os contratos atuais no início do ADR têm precedência.

- **Uso da AWS (registro histórico de 2026-10-25):** a sessão então previa usar créditos do plano Free. A conta foi posteriormente atualizada para Paid; ver a atualização vigente no início deste ADR.
- **Homologação e produção (substitui "um único ambiente"):** o PDF exige deploy automático de homologação e produção. Mesmo cluster EKS e mesma instância RDS, separados por namespace (`auto-shop-hml`, `auto-shop-prd`), database (`autoshop_hml`, `autoshop_prd`), stage do API Gateway (`hml`, `prd`) e target group do ALB. `develop` implanta em hml; `main` implanta em prd. Não há segunda conta, cluster ou RDS. Alta disponibilidade de produção segue fora do escopo.
- **Acesso do CI ao EKS (substitui endpoint privado + CodeBuild):** endpoint público e privado, autenticação por access entries IAM, role OIDC restrita por repositório e branch. Sem runner CodeBuild. Troca registrada: menor isolamento de rede em troca de custo (US$ 0,15/sessão) e de dias de implementação.
- **ALB (substitui ALB criado pelo controller a partir de Ingress):** ALB interno, listener HTTP 80 e dois target groups (hml, prd) são criados no Terraform do `k8s-infra`. O AWS Load Balancer Controller é usado apenas para `TargetGroupBinding`. Motivo: o listener precisa existir no state para ser publicado no SSM e para o destroy não deixar ENIs órfãs.
- **VPC Link V2 → ALB:** HTTP dentro da VPC. A re-criptografia HTTPS até o ALB fica como trabalho futuro. HTTPS público termina no API Gateway.
- **Nodes:** Managed Node Group **On-Demand**, 2 nodes `t3.medium`/`t3a.medium` (min 2, max 2), VPC CNI com prefix delegation e `max_pods=40`. `t3.small` avaliado e descartado: 2 nodes não comportam o pico do HPA. A quota atual aprovada é 16 vCPUs On-Demand e 32 Spot; a Sessão 1 usou On-Demand. Cluster Autoscaler fora do escopo; HPA 1–4 réplicas por namespace, calibrado por carga. **Atualização 2026-10-26 (execução real):** a Sessão 1 confirmou que Spot falhou para o sizing selecionado. [PR #14](https://github.com/Software-Architecture-Group-7-FIAP/k8s-infra/pull/14) alterou o node group para On-Demand. Apply, smoke e destroy concluíram; os 13 checks passaram e não foram encontrados órfãos. O custo de sessão anterior é apenas histórico e deve ser recalculado para o escopo atual.
- **Identidades de banco (decisão histórica, substituída pela atualização vigente):** a proposta anterior tinha três identidades por database: `owner` (master gerenciado pelo RDS, bootstrap e migrations), `app_runtime` (DML, sem DDL) e `lambda_auth` (SELECT nas colunas de cliente). A atualização vigente no início deste ADR define quatro identidades e reserva `owner` ao bootstrap.
- **Domínio e frontend:** mantidos `api.oficina-workshop.com.br` (API Gateway, stages por base path) e `app.oficina-workshop.com.br` / `app-hml.oficina-workshop.com.br` (CloudFront + S3 OAC). WAF com regra gerenciada comum e rate-based por IP em `POST /auth/customer/token` (100 por 5 min, resposta 429) mantido: custo de ~US$ 0,05 por sessão.
- **Notificação serverless (lacuna do PDF):** EventBridge bus, regra para `ServiceOrderProcessingFailed` v1, destino SNS (e-mail) e fila SQS como DLQ, em `auto-shop-system/infra/aws`.
- **Observabilidade:** New Relic, plano gratuito (APM, Kubernetes, Lambda, alertas, dashboards).
- **Swagger:** `/docs` continua fora do Gateway; `openapi.json` gerado no CI e coleção Postman versionados nos repositórios, com link no README.
- **Orçamento:** proposta de sessão ≈ US$ 1,39 (5 h faturadas, nodes spot, sem CodeBuild); plano de 7 sessões ≈ US$ 9. O gatilho de pausa de US$ 10/mês é elevado para **US$ 20/mês em outubro e novembro de 2026**; os alertas de US$ 5, US$ 8 e US$ 10 permanecem como aviso. Esquecer o ambiente ligado custa cerca de US$ 3,80 por noite.
- **Fora do escopo desta fase (trabalho futuro):** TLS até o ALB, Cluster Autoscaler, endpoint EKS privado com runner na VPC, quarta identidade de banco, RDS Proxy, Multi-AZ, produção em conta separada e remoção das Lambdas HS256 administrativas.
- **State:** bucket `auto-shop-tfstate-035611741563-use1` criado em 2026-10-25 (Block Public Access, versionamento, SSE-S3, política TLS-only, expiração de versões não correntes em 30 dias). Lock nativo `use_lockfile=true`. As chaves de state passam a ser `<repo>/staging/terraform.tfstate`.

## Decisões anteriores — históricas, substituídas pelos contratos atuais

### Escopo original de ambientes aprovado em 2026-10-25

- A Fase 3 terá **um único ambiente AWS**, `staging` (homologação), criado para integração e destruído ao final de cada sessão aprovada. O desenvolvimento diário permanece local.
- Produção, uma segunda conta AWS, promoção para produção e requisitos exclusivos de alta disponibilidade de produção ficam fora do escopo atual. Uma futura produção exige decisão e aprovação próprias; não se deve criar `envs/production/` nesta entrega.
- Decisões anteriores que mencionam staging e produção simultaneamente, inclusive sizing Multi-AZ, NAT por AZ, proteção contra exclusão e gates de promoção, ficam substituídas por este escopo para a Fase 3. Referências a produção abaixo são contexto futuro, não critérios de aceite atuais.
- O ambiente único mantém duas AZs, conforme decisão registrada, mas deve minimizar recursos cobrados e tempo ligado. A topologia e o custo por sessão ainda precisam ser aprovados antes de provisionar.

### Repositórios e propriedade

- Renomear o repositório existente `auto-shop-db-cloud-infra` para `database-infra`, preservando sua história e configuração. A issue #69 continua tratando do bootstrap do repositório, mas deve descrever a renomeação como primeiro passo.
- Criar um repositório dedicado `k8s-infra`, conforme a issue #70.
- `k8s-infra` é dono da VPC compartilhada, subnets, rotas, NAT, security group dos nodes EKS e security group dedicado da Lambda; publica IDs não secretos desses recursos no SSM.
- `database-infra` consome os IDs publicados, é dono do subnet group e do security group do RDS, e permite PostgreSQL somente a partir dos security groups dos nodes EKS e da Lambda.
- `lambda-auth` consome do SSM os IDs de subnets privadas e do security group dedicado da Lambda. Isso corresponde ao módulo Terraform atual, que recebe `private_subnet_ids` e `security_group_ids` como entradas e não cria esses recursos de rede.
- O state do banco não deve conter valores de credenciais em claro. Cada repositório mantém seu state remoto e bloqueado, mas os contratos entre `k8s-infra` e `database-infra` são publicados como parâmetros não secretos no SSM Parameter Store, separados por ambiente. O consumidor recebe acesso somente aos nomes/ARNs exatos necessários; não usa `terraform_remote_state`, que exige acesso ao snapshot completo do state.

### Rede e saída

- O único ambiente da fase, staging, terá subnets públicas e privadas em duas AZs; nodes e banco não recebem IP público.
- Staging usa exatamente um NAT Gateway compartilhado na sessão para permitir egress do CodeBuild privado e dos workloads; sua cobrança horária e por tráfego entra integralmente na estimativa e ele é removido no teardown. Não criar NAT por AZ nem deixá-lo ligado fora da sessão.
- Usar gateway endpoints de S3 e DynamoDB sem custo adicional de endpoint. Avaliar interface endpoints caso uma estimativa por região e volume justifique seu custo e operação.
- A aplicação mantém saída HTTPS via NAT para integrações externas existentes e para o JWKS público. A primeira entrega não adiciona proxy nem filtro de egress por domínio.

### EKS e workloads

- O endpoint do control plane EKS fica privado em staging, sem acesso público.
- Fixar Kubernetes `1.37` como baseline de staging, que está em suporte padrão na data desta decisão. Desabilitar suporte estendido; antes de cada sessão, conferir suporte padrão, patch mais recente e compatibilidade dos add-ons e fixar as versões exatas no Terraform/Helm. Não usar versão em suporte estendido.
- GitHub Actions continua como orquestrador. Somente jobs que chamam o Kubernetes API do EKS executam em runners GitHub Actions efêmeros hospedados pelo AWS CodeBuild dentro de subnets privadas da VPC; testes e jobs que não precisam da API Kubernetes permanecem nos runners atuais. Não haverá VM runner persistente. A role de AWS usa OIDC, restrita aos repositórios, workflows e ações necessários, sem access keys estáticas. VPC-enabled CodeBuild precisa de NAT/NAT instance ou endpoints de VPC para acessar dependências públicas; incluir execução, egress e logs no cálculo de custo.
- Staging usa Managed Node Groups com Cluster Autoscaler, inicialmente `min=1`, `desired=1`, `max=2` nodes `t3.medium`; Karpenter fica fora da primeira entrega. HPA começa com `minReplicas=1`, `maxReplicas=2`, CPU 70% e memória 80%, usando os requests/limits já definidos no Deployment como hipótese inicial. Esses números são um limite econômico de homologação, não uma garantia de capacidade ou disponibilidade; carga representativa deve confirmar ou alterar os valores antes de qualquer aceite de desempenho. A homologação prova scale-up de node e agendamento do Pod, não apenas `Pending`.
- Redis será um Deployment efêmero no cluster, sem volume persistente ou serviço ElastiCache. A aplicação acessa somente um Service `ClusterIP`; NetworkPolicy permite a porta Redis apenas aos Pods da aplicação. O pipeline cria uma credencial aleatória por sessão e a injeta em Secret Kubernetes sem exibi-la em logs, estado Terraform ou artefatos. `REDIS_URL` é montada desse Secret; só guarda contadores descartáveis de rate limit e desaparece no teardown.
- E-mail em staging usa MailHog efêmero no namespace da aplicação, SMTP interno na porta 1025 e UI não publicada na Internet. Não há entrega externa nem credenciais SMTP. O código atual classifica `staging` como produção-like e rejeita MailHog; implementar uma exceção explícita e exclusiva para staging, sem relaxar validações de produção, antes do primeiro deploy.
- Habilitar NetworkPolicy nativa do Amazon VPC CNI em modo `strict`. Aplicar negação padrão e políticas explícitas para DNS/CoreDNS, ALB, RDS e serviços AWS necessários. Testar as regras antes da homologação. A saída HTTPS pública permanece permitida pela NAT e não é filtrada por FQDN nesta entrega.
- O security group compartilhado pelos Pods dos nodes é a origem de rede do RDS para a aplicação; NetworkPolicy `strict` limita quais Pods podem conectar. Não usar Security Groups for Pods no baseline `t3.medium`: a família de instâncias `t` não é compatível. O SG dedicado da Lambda é mantido separadamente e referenciado como origem permitida no SG do RDS.

### Banco e identidades

- Usar PostgreSQL 16, alinhado ao `postgres:16-alpine` do ambiente local.
- RDS é privado, PostgreSQL 16, candidato inicial `db.t4g.micro` com 20 GiB gp3, criptografado e Single-AZ em staging. Gustavo decidiu que staging conterá somente dados sintéticos e descartáveis; manter retenção mínima de backup automático durante a sessão para validar recuperação e, no teardown, remover o RDS, backups automatizados e qualquer snapshot, sem snapshot final retido. Classe, storage e custo precisam aparecer no plan e na estimativa aprovada.
- Clientes PostgreSQL devem verificar a cadeia e o hostname do RDS com o bundle CA oficial e `sslmode=verify-full`; `rds.force_ssl` sozinho não substitui a validação do servidor pelo cliente.
- A aplicação, o Job de migrations e a Lambda usam o bundle CA oficial vigente para `us-east-1` e `sslmode=verify-full`; a Lambda deve deixar de forçar `sslmode="require"`. Distribuir o CA como arquivo de runtime e configurar `PGSSLROOTCERT`/`sslrootcert` conforme cada runtime; não incluir CA nem credenciais em `DATABASE_URL` no SSM.
- Classes, armazenamento e região ficam para a etapa de custo e capacidade, antes de qualquer provisionamento. Multi-AZ e proteção de produção não são requisitos desta fase.
- Tornar obrigatório o isolamento de quatro identidades, cada uma com credencial própria: master somente para bootstrap/operação; aplicação runtime com DML e sem DDL; usuário de migrations com DDL necessário ao schema; Lambda com `SELECT` somente nas colunas necessárias da consulta de cliente.
- Manter credenciais separadas por identidade. O segredo master gerenciado pelo RDS conserva o formato gerenciado pela AWS. O Job recebe do segredo `migrations` os campos `username`, `password`, `host` e `port`, valida a identidade e monta a URL de conexão em memória; nenhum valor ou URL de conexão é publicado no SSM.
- Criar e reconciliar usuários/grants com um Job efêmero executado dentro da VPC. O Job lê a credencial master em runtime no Secrets Manager e não recebe nem registra credenciais via Terraform, plan ou logs; o provider PostgreSQL do Terraform não será usado para administrar papéis.
- Usar a senha master gerenciada pelo RDS/Secrets Manager. O Job gera e grava as credenciais de aplicação e migrations em runtime nos segredos previamente criados; valores de senha nunca passam por Terraform, variáveis, state ou logs. Destruir os segredos ao final da sessão.
- External Secrets Operator sincroniza no Kubernetes somente a credencial `app_runtime`. O Job de migrations acessa diretamente o segredo do seu database no Secrets Manager usando uma role Pod Identity e policy limitadas ao ARN exato; não cria nem sincroniza um Secret Kubernetes de migrations. A Lambda lê sua credencial diretamente do Secrets Manager com sua própria role. O master não é sincronizado para workloads normais.
- RDS Proxy fica fora do primeiro deploy de staging. Reavaliar após medir `DatabaseConnections`, concorrência da Lambda e erros de conexão, incluindo o custo por sessão antes de adotá-lo.
- Gerar credenciais novas para cada sessão e removê-las no teardown. Não habilitar rotação automática durante a sessão de até 4 horas; se houver suspeita de exposição, interromper e destruir a sessão inteira e recriá-la com novos segredos. O mecanismo idempotente de criação dos usuários/grants e o formato JSON de cada segredo devem ser definidos antes das issues #76, #80 e #81.

### Entrada pública, Gateway e TLS

- O API Gateway REST regional existente é a única entrada pública da API. Aplicação/ALB não ficam expostos publicamente.
- Usar VPC Link V2 privado do REST API para um ALB interno criado pelo AWS Load Balancer Controller. O ALB encaminha diretamente ao Service da aplicação; o NGINX Ingress permanece apenas no ambiente local.
- As rotas da Lambda de autenticação são integrações diretas do API Gateway e não passam pelo ALB nem pelo authorizer administrativo HS256.
- O staging usa `api.oficina-workshop.com.br` para o API Gateway e `app-hml.oficina-workshop.com.br` para o Angular; produção usa `app.oficina-workshop.com.br`. Gustavo informou que a zona DNS está no Registro.br e tem acesso para editá-la. Validar a delegação e os registros atuais antes de criar novos. O hostname padrão `execute-api` será desabilitado somente após o domínio customizado ser validado. API Gateway continua como única entrada pública da API; ALB e EKS permanecem privados. A região-base é `us-east-1`; o certificado ACM usado pelo CloudFront deve estar nessa região e cobrir os aliases em uso. O Angular é publicado em S3 privado, servido por CloudFront com OAC e HTTPS. Route 53 não é requisito. Antes de certificados/records, aprovar custo e sessão AWS. CORS permite somente a origem do Angular do ambiente correspondente.
- O VPC Link V2 usa HTTPS até o listener 443 do ALB interno. A integração REST define URI `https://api.oficina-workshop.com.br:443`, e API Gateway verifica o hostname/CA do certificado instalado no ALB; não habilitar `insecureSkipVerification`. O listener do ALB encaminha HTTP aos Pods privados dentro da VPC. Usar no ALB o certificado ACM que cobre `api.oficina-workshop.com.br`; não criar outro load balancer.
- Associar AWS WAF ao stage regional, com regras gerenciadas comuns e regra rate-based por IP limitada a `POST /auth/customer/token`, com baseline de 100 requests por 5 minutos por IP e resposta 429 customizada. Manter também throttling do API Gateway em 50 requests/s e burst 100; esses números são limites de proteção inicial, sujeitos à validação funcional e de custo, não promessa de proteção contra abuso distribuído.
- A regra por IP é uma proteção contra abuso concentrado numa origem; não é uma garantia contra abuso distribuído. Não introduzir rate limiter por CPF nesta entrega.
- `/docs`, `/redoc` e `/openapi.json` não serão roteados pelo API Gateway público. A aplicação os mantém acessíveis somente pela rede privada do ALB para diagnóstico operacional; não incluir rota pública ou cache CloudFront para esses paths.

### Deploy e integração

- A migration precisa concluir antes de iniciar o rollout da aplicação; falha de migration interrompe o deploy, sem atualizar o Deployment. A execução usa a credencial de migrations e preserva o mecanismo de advisory lock.
- Os manifests referenciam imagens por digest. Rollback reverte a versão da aplicação, não desfaz migrations; migrations devem seguir expand/contract para permitir convivência entre versões.
- Pessoa 2 entrega VPC/rede, EKS, ALB interno, RDS e IAM de infraestrutura; a Pessoa 3, dona da issue #88 e da configuração existente em `auto-shop-system/infra/aws`, coordena as mudanças no API Gateway/WAF com os IDs e security groups fornecidos pela Pessoa 2. Pessoa 1 valida contratos de JWT, rotas, banco e evento; Pessoa 3 valida consumo e alertas do evento. O cenário integrado de staging só fecha após evidências sanitizadas reproduzíveis.
- CI com mocks não substitui a homologação real de staging. O relatório registra commits/digests e revisão Alembic, sem CPF, JWT, senha, conexão ou material criptográfico.

## Consequências históricas

- A entrada pública centralizada preserva WAF e throttling do Gateway e remove o caminho que permitiria contornar suas regras via Ingress público. Os subdomínios dedicados separam Angular e API; o domínio e DNS controlados são uma dependência de staging. TLS é verificado até o ALB interno; somente o salto privado entre ALB e Pods usa HTTP.
- O ALB interno acrescenta o custo e a operação de um load balancer, mas elimina um proxy NGINX redundante no caminho cloud.
- Um NAT compartilhado reduz custo de staging, mas pode limitar a saída durante falha da AZ que o hospeda; desligar a infraestrutura após a sessão reduz o custo ocioso, não o custo durante a execução.
- NetworkPolicy `strict` reduz tráfego lateral, mas qualquer Pod selecionado precisa das permissões explícitas desde sua inicialização, incluindo CoreDNS.
- Quatro credenciais melhoram atribuição e contenção de privilégios, ao custo de bootstrap e contratos de segredo separados.
- O escopo atual não inclui banco Multi-AZ de produção.
- A limitação por IP e throttling não prometem uma cota rígida de custo nem mitigação completa de ataques distribuídos.

## Lista histórica de ajustes nas issues — revalidar antes de agir

As issues abertas preservam seu histórico. Antes de implementar, os critérios devem refletir as decisões acima; a issue #69 permanece como está, conforme preferência registrada, e a ação é renomear o repositório existente.

- **#69–#70:** executar a renomeação de `auto-shop-db-cloud-infra` para `database-infra`, preservando história e configurações, sem criar um segundo repositório de banco; #70 cria o repositório novo `k8s-infra`.
- **#71–#73:** declarar VPC/rede compartilhada como propriedade de `k8s-infra`, um único ambiente AWS de staging e o contrato SSM desse ambiente. Remover a dependência de `terraform_remote_state`; o banco consome subnets/identificadores e cria seus próprios recursos de rede para RDS.
- **#72 e #90:** o EKS usa endpoint público e privado com autenticação por IAM access entries; não usar runner CodeBuild. Jobs GitHub Actions hospedados usam OIDC com trust restrita ao repositório/branch e permissões mínimas. A publicação do Angular usa role própria limitada ao bucket do ambiente e à invalidação da distribuição CloudFront. Kubernetes `1.37` é a baseline; patch, add-ons e permissões exatas são fixados/revalidados antes da sessão.
- **#74 e #78:** separar autoscaling de nodes (Managed Node Groups + Cluster Autoscaler em staging, 1–2 `t3.medium`) do HPA de Pods (1–2 réplicas, CPU 70%, memória 80%). O teste de node scaling deve observar scale-up e agendamento bem-sucedidos; `Pending` isolado não é aceite. Os limites são um baseline de custo, não uma medição de capacidade.
- **#75–#76 (texto histórico, substituído):** o escopo antigo não corresponde ao contrato vigente de quatro identidades por database (`owner`, `app_runtime`, `migrations`, `lambda_auth`), registrado no início do ADR; manter o RDS Single-AZ e o privilégio mínimo. `owner` fica exclusivo do bootstrap.
- **#77:** manter default-deny desde o início em modo `strict`, com políticas explícitas para DNS/CoreDNS, ALB, RDS e dependências AWS. A instrução de começar permissivo deve ser removida; a validação ocorre com políticas prontas antes de habilitar workloads.
- **#79, #88 e #113:** API Gateway REST Regional é a entrada pública da API em `api.oficina-workshop.com.br`; frontend Angular fica em S3 privado + CloudFront OAC (`app-hml.` e `app.`), com ACM e DNS controlado pelo grupo. O VPC Link V2 usa HTTP dentro da VPC até o ALB interno, e o ALB usa HTTP apenas aos Pods privados; a terminação HTTPS pública ocorre no API Gateway. Remover Ingress público/NLB/NGINX do caminho cloud; desabilitar `execute-api` somente após smoke do domínio; manter `/docs`, `/redoc` e `/openapi.json` privados. O Terraform atual em `auto-shop-system/infra/aws` ainda é o gateway legado; o delta de VPC Link, integração Lambda, domínios e WAF segue em #113.
- **#80 (contrato vigente):** limitar ESO à credencial `app_runtime`; o Job de migrations lê diretamente seu segredo no Secrets Manager com policy IAM por ARN exato. A Lambda acessa seu segredo por role própria; master não é sincronizado para workloads.
- **#81–#82:** publicar apenas parâmetros não secretos no SSM por ambiente, com leitura por nomes/ARNs exatos. #81 deve expor as referências aos segredos das identidades sem credenciais; #82 deve expor os IDs necessários de VPC, subnets, cluster, OIDC e ALB interno, sem `ingress_hostname` público.
- **#83:** retirar RDS Proxy do escopo do primeiro deploy e tratar sua adoção como decisão posterior baseada em métricas e custo.
- **#84–#86:** usar a credencial de migrations no Job, interromper o deploy se a migration falhar e exigir digest de imagem. Rollback reverte a aplicação; mudanças de schema devem seguir expand/contract, sem prometer rollback automático de banco ou ausência absoluta de downtime.
- **#85:** implementar `sslmode=verify-full` e CA oficial para app, migrations e Lambda, além de `rds.force_ssl`; substituir o override Lambda `sslmode="require"`.
- **#87:** substituir “conta limpa” por execução repetível no único ambiente staging aprovado e com custos/recursos autorizados; destruir workload, snapshots e backups na ordem correta. O bucket S3 de state persiste com custo próprio e precisa de retenção/backup separado. A evidência de escala distingue HPA e Cluster Autoscaler.
- **#95 e #98:** substituir a referência a quatro repositórios por `auto-shop-system` (backend + frontend), `lambda-auth`, `database-infra` e `k8s-infra`; atualizar o grafo de dependências, ligar este ADR e alinhar o caminho de ADRs com `docs/architecture/decisions/`. O roteiro integrado não deve tratar CI com mocks como homologação de staging.

## Registros operacionais históricos da Etapa 0

### Conta AWS do staging

- A conta identificada é **Oficina Workload - 16SOAT**, ID `837155819003`.
- A intenção inicial era usar esta conta para staging e produção, mas essa escolha foi suspensa em 2026-10-25: Gustavo confirmou que o participante que saiu do grupo controla o e-mail raiz, todos os meios de recuperação e a conta de gerenciamento/faturamento da organização.
- A conta `837155819003` não será usada pela Fase 3 enquanto permanecer sob esse controle. Só poderá ser reconsiderada se a governança e os meios de recuperação forem transferidos integralmente para o grupo ativo e o acesso do ex-participante for removido.
- Decisão aprovada em 2026-10-25: a nova conta será **standalone**, sem AWS Organization nesta fase. O motivo é manter uma única conta de workload e preservar a elegibilidade ao plano Free/créditos. Nesta fase, Gustavo é o único operador humano com acesso direto; não criar identidades adicionais nem compartilhar credenciais. Reavaliar o modelo de acesso humano se a equipe precisar de acesso direto ou se surgirem múltiplas contas.
- A conta nova foi criada com outro e-mail e ID `035611741563`. Gustavo confirmou que o grupo ativo controla o e-mail raiz, que o MFA da raiz está ativo e que não há Organization; a API AWS também retornou `AWSOrganizationsNotInUseException`. O plano é Free até 2026-11-06 ou até o esgotamento dos créditos, com US$ 120 restantes conforme o console em 2026-10-25; os contatos alternativos Billing, Security e Operations foram cadastrados pelo grupo. O escopo aprovado é um único staging efêmero; não há conta ou workload de produção nesta fase.
- O IAM user `gustavo-ferreira` pertence ao grupo `admin`, que anexa `AdministratorAccess`; o usuário também tem `IAMUserChangePassword` diretamente, MFA virtual ativo e nenhuma access key. O resumo da conta confirmou 1 usuário, 1 grupo, 3 roles, MFA habilitado e zero access keys. Gustavo escolheu manter esse perfil administrativo para validações, com uso limitado a consultas nesta etapa; roles de CI/CD e workloads continuam sujeitas a desenho de menor privilégio. Gustavo é o único membro da equipe com acesso direto ao console/CLI nesta fase; os demais trabalham por PRs e pipelines com OIDC restrito aos repositórios e workflows necessários. Nenhuma mutação AWS ou `terraform apply` está autorizada sem aprovação específica conforme ADR-0064. Gustavo confirmou que o grupo ativo possui acesso e recuperação da raiz documentados; não registrar no Git os endereços, números ou segredos de recuperação. O inventário IAM sanitizado da conta anterior e o plano de reprodução seletiva estão em [`docs/architecture/aws-iam-inventory-conta-anterior.md`](../aws-iam-inventory-conta-anterior.md).
- O AWS CLI v2.38.5 foi autenticado por `aws login --remote` no perfil `oficina-workload`, com região padrão `us-east-1`. Em 2026-10-25, `sts get-caller-identity` confirmou `Account=035611741563` e `Arn=arn:aws:iam::035611741563:user/gustavo-ferreira`; a sessão temporária não depende de access keys persistentes. A inspeção de recursos da conta antiga foi interrompida antes de consultar qualquer recurso.
- Os budgets `Budget-Oficina` (US$ 10), `monthly_5_dollars_budget` (US$ 5) e `zero_spend_budget` (US$ 1) existem. `Budget-Oficina` contém notificações mensais de custo real acima de US$ 5, US$ 8 e US$ 10, sem budget actions. A consulta exata da AWS confirmou que o endereço escolhido por Gustavo já está inscrito nos três limites; nenhuma alteração foi necessária. O endereço não é repetido neste ADR. A entrega ao inbox não foi testada, e as notificações podem atrasar; elas não limitam nem interrompem gasto.
- A decisão de 2026-10-25 de usar apenas o hostname padrão do API Gateway foi substituída após Gustavo aprovar a preparação de API e frontend com domínio próprio. O domínio é `oficina-workshop.com.br`, com DNS no Registro.br e acesso de edição confirmado por Gustavo. Usar `api.oficina-workshop.com.br` e `app.oficina-workshop.com.br`, API Gateway Regional + ACM e CloudFront + S3 privado; Route 53 é opcional. Validar delegação e registros existentes antes da sessão autorizada. A integração VPC Link V2–ALB usa HTTPS com validação de hostname; o ALB encaminha HTTP somente aos Pods privados.
- A imagem da sessão da conta anterior mostra um papel federado `AWSReservedSSO_AdminPlataforma_*`, criado pelo IAM Identity Center. Isso comprova uma atribuição de acesso federado naquela conta, mas não transfere controle do usuário raiz, meios de recuperação, conta de gerenciamento da AWS Organization ou faturamento.
- Esta decisão define o escopo dos ambientes, mas não autoriza provisionamento ou deploy. Chamadas AWS somente de leitura dependem de autorização expressa; a execução de staging exige validação operacional conforme o ADR-0064.
- O sizing final dos recursos, o custo por sessão e o procedimento de teardown ainda precisam ser validados antes de qualquer ação potencialmente cobrável. Os dados de staging são sintéticos e não serão preservados após o teardown.

### Critério de seleção da região

- A prioridade informada é reduzir custo regional. Foi aceito usar uma região US East para o único ambiente AWS desta fase.
- `us-east-1` é a região-base escolhida para staging. `us-east-2` será comparada depois com o mesmo dimensionamento e perfil de uso, antes de aprovar os custos; não se presume que uma delas seja sempre mais barata para todos os serviços.
- O Terraform atual em `auto-shop-system/infra/aws` usa `us-east-1` como padrão em `variables.tf` e `terraform.tfvars.example`. Isso é um padrão de código, não confirmação da região de recursos implantados.
- Latência e localização dos dados devem ser avaliadas para decidir se a região-base atende à demonstração a partir do Brasil. Não há gate de produção nesta fase.
- API Gateway, VPC Link e ALB devem ser alinhados à região escolhida para a integração privada.

### Disponibilidade por zona

- O único ambiente staging usará exatamente duas Availability Zones, conforme decisão registrada. A rede terá subnets públicas e privadas nas duas AZs.
- Não provisionar NAT por AZ nem RDS Multi-AZ como requisitos de produção nesta fase; eventual necessidade futura exige novo dimensionamento e aprovação.
- Plano de endereçamento proposto e escolhido para validação no plan: VPC `10.80.0.0/20`; subnets públicas/NAT `10.80.0.0/27` (AZ A) e `10.80.0.32/27` (AZ B); faixas antes reservadas para CodeBuild (`10.80.0.64/27` e `10.80.0.96/27`) permanecem não alocadas; workloads EKS/ALB e ENIs da Lambda `10.80.2.0/23` e `10.80.4.0/23`; RDS isolado `10.80.6.0/24` e `10.80.7.0/24`. Ranges não se sobrepõem e deixam `10.80.8.0/21` sem alocação. Selecionar duas AZ IDs suportadas em `us-east-1` (excluir `use1-az3`) e registrar o mapeamento nome/ID no plan. Um NAT Gateway fica na subnet pública da AZ A; as duas subnets privadas de workload usam sua rota, e as subnets RDS não têm rota default. O plano não reutiliza `172.31.0.0/16`. Esta decisão fecha o desenho; validar capacidade/IPs no plan continua como gate de execução.

### Referência preliminar de custo de staging

- Gustavo informou que este é um projeto educacional e que o gasto deve ficar o mais próximo possível do Free Tier. O cenário 24x7 abaixo serve apenas para mostrar o custo de manter os recursos ligados continuamente; não é o modo de operação aprovado.
- Gustavo definiu **US$ 10/mês como gatilho para pausar novas sessões de staging**. Isso é um limite operacional de alerta, não um teto garantido: AWS Budgets pode atrasar e recursos existentes continuam gerando custos até o teardown.
- Cenário de referência 24x7 em `us-east-1`: um cluster EKS em suporte padrão, um NAT Gateway, um ALB interno, dois nodes EC2 `t3.medium` e um RDS PostgreSQL Single-AZ `db.t4g.micro`.
- Com 730 horas por mês e tarifas públicas sob demanda consultadas em 2026-10-25, o subtotal das tarifas horárias é **US$ 194,69/mês**: EKS US$ 73,00; NAT US$ 32,85; ALB US$ 16,43; dois nodes US$ 60,74; RDS US$ 11,68.
- É uma referência de sizing, não uma aprovação de custo nem uma estimativa final. Exclui EBS, armazenamento e backups do RDS, processamento/transferência de dados, LCUs do ALB, IPv4, CloudWatch, Secrets Manager, KMS, impostos e eventuais créditos/descontos. O valor final deve ser refeito no AWS Pricing Calculator com o sizing aprovado antes de qualquer provisionamento.
- A tela consultada em 2026-10-25 mostra plano Free terminando em 2026-11-06 ou quando os créditos acabarem, o que ocorrer primeiro, com saldo de US$ 120. `Budget-Oficina` tem alertas de custo real acima de US$ 5, US$ 8 e US$ 10; a AWS confirmou o destinatário já cadastrado em todos eles. A métrica `CostTypes` não está explicitamente configurada no objeto consultado. Ao atingir US$ 10, pausar novas sessões. Isso não substitui teardown e os budgets não impõem teto rígido.
- Gustavo aprovou um único staging AWS efêmero: criar os recursos somente durante integração/homologação e destruí-los ao final; o desenvolvimento diário permanece local. Produção fica fora do escopo atual. Cada sessão terá no máximo 4 horas, teardown no mesmo dia e nenhum recurso deixado ligado durante a noite. O conjunto de recursos e a estimativa completa de custo ainda precisam ser validados antes de provisionar.
- A tela da conta confirma plano Free, US$ 120 de saldo e encerramento do acesso Free em 2026-11-06 ou quando os créditos acabarem, o que ocorrer primeiro. A documentação da AWS informa que a conta Free é fechada no fim do plano, os recursos ficam inacessíveis e a conta pode ser reaberta por upgrade para Paid dentro de 90 dias; créditos restantes são aplicados a cobranças elegíveis depois do upgrade. Gustavo decidiu não fazer upgrade e continuar o desenvolvimento local. Não criar recursos AWS para esta fase antes do fim do plano sem uma aprovação específica; para retomar staging depois, será necessário revisar custos, aprovar o upgrade e a sessão de execução. O catálogo da AWS lista EKS entre os serviços incluídos no Free Tier da nova experiência de cadastro, mas permissões, recursos específicos e quotas ainda devem ser validados na própria conta antes de provisionar.

### VPCs default da conta anterior (fora da Fase 3)

- Em 2026-10-25, uma inspeção somente de leitura confirmou a conta `837155819003` e verificou que `vpc-0cd91fe72dec2c2d7` existe em `us-east-2`, com CIDR IPv4 `172.31.0.0/16`, estado `available`, `IsDefault=true` e sem tags.
- A conta também possui em `us-east-1` a VPC default `vpc-00323d1ff796a271a`, com o mesmo CIDR `172.31.0.0/16`. As duas VPCs estão em regiões distintas e usam CIDRs iguais; a AWS não permite VPC Peering entre VPCs com CIDRs sobrepostos. Redes locais/VPN também precisam ser inventariadas para evitar conflitos de rota; não assumir conectividade sem avaliar renumeração ou tradução.
- A VPC de `us-east-2` tem três subnets default (`172.31.0.0/20`, `172.31.16.0/20` e `172.31.32.0/20`) nas AZs `us-east-2a`, `us-east-2b` e `us-east-2c`; todas habilitam atribuição de IP público no lançamento.
- A tabela de rotas principal envia `0.0.0.0/0` ao Internet Gateway `igw-0b59994df55c36913`; não há NAT Gateway. O DNS support e DNS hostnames estão habilitados.
- A network ACL default permite todo o tráfego IPv4 de entrada e saída; o security group default permite entrada apenas do próprio grupo e toda saída IPv4. A inspeção não encontrou ENIs, VPC endpoints, peering, anexos a Transit Gateway nem VPC Flow Logs na VPC de `us-east-2`.
- Uma segunda inspeção somente de leitura em `us-east-1` e `us-east-2` não encontrou conexões Site-to-Site VPN, Customer Gateways, VPN Gateways, Transit Gateways, anexos a TGW ou VPC Peering. Portanto, não há conexões AWS híbridas ou entre VPCs registradas nessas regiões; isso não confirma as faixas da rede local nem conexões fora da conta/regiões consultadas.
- Gustavo confirmou que este é um projeto de aprendizado sem oficina/local físico. Não há rede local a integrar; a Fase 3 será cloud-only e não exige VPN nesta etapa.
- Decisão: não reutilizar as VPCs default para a Fase 3; a infraestrutura usará a VPC dedicada `10.80.0.0/20` e o plano de subnets proposto em “Disponibilidade por zona”. Como não há rede local a conectar, validar somente os ranges e a capacidade no Terraform plan antes de provisionar.

### Inventário inicial da conta substituta

- Em 2026-10-25, após confirmação via STS da conta `035611741563`, foram consultadas somente APIs de leitura em `us-east-1` e `us-east-2`.
- A conta possui uma VPC default em cada região consultada, ambas com CIDR `172.31.0.0/16`: `vpc-0f8d1286cb7e91f74` em `us-east-1` e `vpc-0620bd437e2fc4bfc` em `us-east-2`. Em `us-east-1`, há seis subnets default, uma por AZ (`us-east-1a` a `us-east-1f`), todas com `MapPublicIpOnLaunch=true`; essas redes públicas não atendem à topologia privada aprovada.
- Na região-base `us-east-1`, as APIs consultadas não retornaram EKS clusters, instâncias RDS, NAT Gateways, load balancers ELBv2, funções Lambda ou REST APIs do API Gateway. Isso é um inventário limitado a esses serviços e não afirma que toda a conta esteja vazia.
- Não reutilizar as VPCs default. A rede da Fase 3 continuará dedicada, em `us-east-1`, com duas AZs e plano `10.80.0.0/20`; validar CIDR/subnets após fechar sizing de EKS e antes de provisionar.

## Contratos técnicos atuais entre repositórios

### VPC e subnets

O bloco e as faixas estão definidos acima. `workload-private-subnet-ids` é a mesma dupla de subnets `/23` para EKS, ALB interno e Lambda; os Security Groups separam as permissões. Isso evita criar uma terceira dupla de subnets apenas para Lambda. `rds-isolated-subnet-ids` permanece separado por rota e função. Não há subnets para CodeBuild, que foi removido do desenho vigente.

### Contrato SSM entre repositórios

Todos os parâmetros abaixo são Standard `String` ou `StringList`, região `us-east-1`, prefixo `/auto-shop/staging`; nenhum valor secreto é armazenado no SSM. Consumidores usam nomes explícitos e `GetParameter`/`GetParameters` por ARN exato, sem `GetParametersByPath` amplo e sem `terraform_remote_state`.

| Nome do parâmetro | Tipo | Publicador | Leitores/uso |
|---|---|---|---|
| `/auto-shop/staging/network/vpc-id` | `String` | `k8s-infra` | `database-infra`; `lambda-auth` quando o módulo precisar da VPC |
| `/auto-shop/staging/network/workload-private-subnet-ids` | `StringList` | `k8s-infra` | `database-infra` para regra de rede, `lambda-auth` para a Lambda; contém as duas subnets `/23` |
| `/auto-shop/staging/network/rds-isolated-subnet-ids` | `StringList` | `k8s-infra` | `database-infra` |
| `/auto-shop/staging/network/eks-node-security-group-id` | `String` | `k8s-infra` | `database-infra` para ingress PostgreSQL; nenhum acesso humano de runtime |
| `/auto-shop/staging/network/lambda-security-group-id` | `String` | `k8s-infra` | `database-infra` para ingress PostgreSQL e `lambda-auth` |
| `/auto-shop/staging/eks/cluster-name` | `String` | `k8s-infra` | role OIDC de deploy em `k8s-infra` |
| `/auto-shop/staging/eks/oidc-provider-arn` | `String` | `k8s-infra` | roles de workload/ESO e pipeline de deploy em `k8s-infra` |
| `/auto-shop/staging/domain/root` | `String` | `k8s-infra`, a partir de `root_domain` | pipelines `auto-shop-system`, `lambda-auth` e Gateway para compor hostnames |
| `/auto-shop/staging/domain/api-url` | `String` | `k8s-infra` | app, `lambda-auth` e `auto-shop-system/infra/aws` |
| `/auto-shop/staging/domain/frontend-url` | `String` | `k8s-infra` | app e pipeline de publicação do Angular |
| `/auto-shop/staging/gateway/internal-alb-listener-arn` | `String` | `k8s-infra` após criar o ALB | `auto-shop-system/infra/aws` para a integração VPC Link |
| `/auto-shop/staging/auth/customer-token/function-arn` | `String` | `lambda-auth` | `auto-shop-system/infra/aws` para integração direta do API Gateway |
| `/auto-shop/staging/database/host` | `String` | `database-infra` | workflows de deploy de `k8s-infra` e `lambda-auth` materializam a configuração da aplicação/Lambda |
| `/auto-shop/staging/database/port` | `String` | `database-infra` | workflows de deploy de `k8s-infra` e `lambda-auth` |
| `/auto-shop/staging/database/security-group-id` | `String` | `database-infra` | `lambda-auth` para validar a regra de rede; infraestrutura de aplicação se necessário |
| `/auto-shop/staging/database/names/hml` | `String` | `database-infra` | deploy de homologação em `k8s-infra` e `lambda-auth` |
| `/auto-shop/staging/database/names/prd` | `String` | `database-infra` | deploy de produção em `k8s-infra` e `lambda-auth` |
| `/auto-shop/staging/database/secrets/runtime-hml-arn` | `String` | `database-infra` | ESO em `k8s-infra` lê o secret exato de runtime hml |
| `/auto-shop/staging/database/secrets/runtime-prd-arn` | `String` | `database-infra` | ESO em `k8s-infra` lê o secret exato de runtime prd |
| `/auto-shop/staging/database/secrets/lambda-hml-arn` | `String` | `database-infra` | `lambda-auth` lê o secret exato de hml |
| `/auto-shop/staging/database/secrets/lambda-prd-arn` | `String` | `database-infra` | `lambda-auth` lê o secret exato de prd |
| `/auto-shop/staging/database/secrets/migrations-hml-arn` | `String` | `database-infra` | Job de migrations HML em `auto-shop-system`; identidade DDL exclusiva de `autoshop_hml` |
| `/auto-shop/staging/database/secrets/migrations-prd-arn` | `String` | `database-infra` | Job de migrations PRD em `auto-shop-system`; identidade DDL exclusiva de `autoshop_prd` |
| `/auto-shop/staging/database/secrets/owner-arn` | `String` | `database-infra` | somente o Job de bootstrap em `database-infra` lê o master gerenciado pelo RDS |
| `/auto-shop/staging/database/iam/migrations-hml-read-policy-arn` | `String` | `database-infra` | role Pod Identity HML de `auto-shop-system`, limitada ao segredo migrations HML |
| `/auto-shop/staging/database/iam/migrations-prd-read-policy-arn` | `String` | `database-infra` | role Pod Identity PRD de `auto-shop-system`, limitada ao segredo migrations PRD |
| `/auto-shop/staging/database/iam/lambda-read-policy-arn/hml` | `String` | `database-infra` | role da Lambda hml em `lambda-auth` |
| `/auto-shop/staging/database/iam/lambda-read-policy-arn/prd` | `String` | `database-infra` | role da Lambda prd em `lambda-auth` |
| `/auto-shop/staging/auth/customer-jwt/issuer` | `String` | `lambda-auth` | aplicação valida `CUSTOMER_JWT_ISSUER` |
| `/auto-shop/staging/auth/customer-jwt/audience` | `String` | `lambda-auth` | aplicação valida `CUSTOMER_JWT_AUDIENCE` |
| `/auto-shop/staging/auth/customer-jwt/jwks-url` | `String` | `lambda-auth` | aplicação valida JWT via `CUSTOMER_JWT_JWKS_URL` |
| `/auto-shop/staging/events/service-order-bus-name` | `String` | `auto-shop-system/infra/aws` | aplicação; seu IAM só recebe `events:PutEvents` no ARN do bus |

`database-infra` publica somente endpoint/porta/nomes/IDs/ARNs e ARNs de policies; nunca publica valores de credenciais ou `DATABASE_URL`. O master `owner`, as credenciais `app_runtime`, `migrations` e `lambda_auth` vivem no Secrets Manager, cada uma em seu ARN. Somente o bootstrap acessa `owner`; as roles de migrations HML e PRD do `auto-shop-system` recebem cada uma a policy de leitura do segredo correspondente. Credenciais Redis são geradas por sessão diretamente no cluster e não são publicadas no SSM.

### Terraform state e locking

O bucket S3 privado de state em `us-east-1` usa Block Public Access, versionamento, política TLS-only, SSE-S3 e lock nativo `use_lockfile=true` (Terraform >=1.10), sem tabela DynamoDB. As chaves são separadas por root Terraform: `k8s-infra/staging/terraform.tfstate`, `database-infra/staging/terraform.tfstate`, `lambda-auth/staging/terraform.tfstate` e `auto-shop-system/infra/aws/staging/terraform.tfstate`. Roles OIDC de cada root acessam somente seu state e `.tflock`. O bucket persiste entre sessões, tem custo próprio e não é destruído no teardown do staging.

### Identidade JWT e entrada pública

O contrato do JWT de cliente fica alinhado nos dois repositórios: issuer `https://api.oficina-workshop.com.br`, audience `auto-shop-api`, JWKS `https://api.oficina-workshop.com.br/.well-known/jwks.json`, algoritmo RS256 com assinatura em KMS e `kid` igual no token e no JWKS. Criar uma chave de assinatura por sessão e usar `kid=staging-<session-id>` único; tokens não sobrevivem ao teardown. No teardown, agendar exclusão da chave KMS com a janela mínima de sete dias; ela fica desabilitada durante a espera. A AWS não cobra armazenamento mensal por uma chave marcada para exclusão; contabilizar as chamadas KMS que excedam a faixa gratuita. RDS/Secrets Manager usam as chaves gerenciadas pela AWS quando compatíveis, evitando CMKs adicionais. A aplicação consome as referências públicas do SSM, nunca a chave privada. A chave KMS e os segredos de banco não são publicados no SSM.

O Angular usa `https://app-hml.oficina-workshop.com.br` em homologação e `https://app.oficina-workshop.com.br` em produção; CORS permite somente a origem do ambiente correspondente. O API Gateway usa `api.oficina-workshop.com.br` com base paths separados para `hml` e `prd`. CloudFront serve os arquivos de cada ambiente de seu bucket S3 privado via OAC. O certificado ACM anexado ao CloudFront fica em `us-east-1` e cobre os aliases usados; certificados regionais do API Gateway/ALB são independentes quando necessário. DNS ficará no Registro.br; validar delegação e registros atuais antes de publicar os CNAMEs de validação e destino. Desabilitar `execute-api` somente após domínio e smoke test ativos.

## Gatilhos técnicos e de aprovação antes de uma futura sessão AWS

O desenho técnico está fechado. O estado Paid da conta não autoriza mudanças nela, criação de recursos, `terraform apply` ou deploy. O ADR-0064 continua exigindo aprovação específica antes dessas ações.

**Decisões fechadas para implementação:** uma infraestrutura AWS `staging` efêmera com logical `hml`/`prd`; `us-east-1` como base; duas AZ IDs; VPC/subnets definidas acima; EKS `1.37` com endpoint público e privado, IAM access entries, sem CodeBuild; sizing inicial de 2 nodes a revalidar por custo; PostgreSQL 16 `db.t4g.micro`/20 GiB gp3/Single-AZ; três identidades por database; tabela SSM com donos e leitores; S3 state com lock nativo; `verify-full` e CA oficial; API Gateway `api.oficina-workshop.com.br`; Angular em CloudFront/S3 com aliases `app.` e `app-hml.`; domínio e WAF mantidos; WAF Regional 100/5 min no POST de token, WAF `CLOUDFRONT` separado, e throttling Gateway 50/100.

**Pendências de implementação/validação, não novas escolhas de arquitetura:**

1. Atualizar `auto-shop-system` e `lambda-auth` para `sslmode=verify-full` e CA; adicionar overlay staging do MailHog com exceção de configuração limitada a staging e Redis sem PVC/ElastiCache com NetworkPolicy restrita.
2. Implementar o frontend em S3 privado + CloudFront/OAC, os custom domains do API Gateway, certificado ACM e CORS. O domínio está no Registro.br e Gustavo confirmou acesso de edição; após aprovação de custo, validar delegação e registros existentes antes de publicar os CNAMEs necessários.
3. Implementar exatamente os nomes SSM acima e políticas de leitura por parâmetro/secret ARN; definir o valor físico do nome do bucket (globalmente único) na execução autorizada. O state bucket, chamadas KMS, CloudFront, WAF Regional e WAF `CLOUDFRONT`, Gateway, EKS, NAT, RDS, logs, IPv4 e teardown entram no AWS Pricing Calculator; não incluir CodeBuild. A chave KMS fica sem uso e marcada para exclusão por sete dias após teardown, sem tarifa mensal de armazenamento durante esse período. Remover os secrets descartáveis com exclusão imediata sem recovery window após confirmar o teardown, conforme a retenção aprovada para dados sintéticos.
4. Fixar patch/add-ons/AMIs e validar quotas/AZ IDs e as faixas no Terraform plan; a versão `1.37` deve continuar em suporte padrão. Comparar o mesmo sizing em `us-east-2` antes da aprovação de custo. Calibrar HPA/WAF com evidência representativa; os valores definidos são limites iniciais de staging.
5. Confirmar com Pessoa 1 o issuer/audience/JWKS e com Pessoa 3 as rotas Gateway, assinatura da integração privada e pipeline; `/docs`, `/redoc` e `/openapi.json` ficam fora da entrada pública.
6. Atualizar a estimativa da sessão, incluindo create/teardown, registro/renovação do domínio, DNS/certificado, CloudFront, WAF e recursos persistentes; máximo 5 h, teardown no mesmo dia, dados sintéticos e sem snapshot final. O baseline horário antigo de US$ 0,27/h e US$ 1,07/4 h exclui recursos relevantes e não é estimativa final nem aprovação. Reconfirmar saldo de créditos e custo antes de qualquer sessão; `terraform apply` exige autorização específica.

As referências abaixo registram as restrições técnicas usadas para fechar esses contratos. A disponibilidade de versões, quotas, preços e o domínio devem ser reconfirmados antes da execução.

## Referências

- ADR-0064: salvaguarda de provisionamento AWS e contrato JWT.
- Issues #69–#87 do repositório `auto-shop-system`.
- [API Gateway REST: integração privada](https://docs.aws.amazon.com/apigateway/latest/developerguide/private-integration.html)
- [API Gateway REST: associação do AWS WAF](https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-control-access-aws-waf.html)
- [API Gateway: limites de throttling](https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-request-throttling.html)
- [VPC Peering: limitações de CIDRs sobrepostos](https://docs.aws.amazon.com/vpc/latest/peering/vpc-peering-basics.html)
- [EKS: ALB Ingress](https://docs.aws.amazon.com/eks/latest/userguide/alb-ingress.html)
- [EKS: Network Policies do VPC CNI](https://docs.aws.amazon.com/eks/latest/userguide/cni-network-policy-configure.html)
- [RDS: Multi-AZ com standby](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Concepts.MultiAZSingleStandby.html)
- [RDS Proxy: cenários de uso](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/rds-proxy-best-practices.usage-scenarios.html)
- [Preços do Amazon EKS](https://aws.amazon.com/eks/pricing/)
- [Preços do Amazon VPC e NAT Gateway](https://aws.amazon.com/vpc/pricing/)
- [Preços do Application Load Balancer](https://aws.amazon.com/elasticloadbalancing/pricing/)
- [Preços sob demanda do Amazon EC2](https://aws.amazon.com/ec2/pricing/on-demand/)
- [Preços do Amazon RDS para PostgreSQL](https://aws.amazon.com/rds/postgresql/pricing/)
- [AWS Free Tier: perguntas frequentes e elegibilidade](https://aws.amazon.com/free/free-tier-faqs/)
- [AWS: comparar as opções de cadastro](https://docs.aws.amazon.com/accounts/latest/reference/sign-up-for-aws.html)
- [AWS Billing: escolher o plano Free ou Paid](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/free-tier-plans.html)
- [AWS: serviços suportados no plano Free da experiência nova](https://docs.aws.amazon.com/accounts/latest/reference/supported-services-sign-up-new.html)
- [AWS Budgets: criar um orçamento de custo](https://docs.aws.amazon.com/cost-management/latest/userguide/create-cost-budget.html)
- [IAM Identity Center: capacidades das instâncias standalone e Organization](https://docs.aws.amazon.com/singlesignon/latest/userguide/identity-center-instances.html)
- [AWS CLI: login local com credenciais do console](https://docs.aws.amazon.com/signin/latest/userguide/command-line-sign-in.html)
- [AWS Budgets: monitorar custos e atraso das notificações](https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-managing-costs.html)
- [AWS Account Management: editar contatos alternativos](https://docs.aws.amazon.com/accounts/latest/reference/manage-acct-update-contact-alternate.html)
- [IAM: criar um usuário e recomendações para credenciais](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_users_create.html)
- [AWS CLI: autenticar localmente com credenciais do console](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sign-in.html)
- [AWS IAM: política gerenciada SignInLocalDevelopmentAccess](https://docs.aws.amazon.com/aws-managed-policy/latest/reference/SignInLocalDevelopmentAccess.html)
- [AWS IAM: práticas recomendadas de segurança](https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html)
- [AWS IAM: policy gerenciada AdministratorAccess](https://docs.aws.amazon.com/aws-managed-policy/latest/reference/AdministratorAccess.html)
- [AWS IAM: atribuir MFA virtual a um usuário](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_mfa_enable_virtual.html)
- [AWS Account Management: convidar membros na nova experiência AWS](https://docs.aws.amazon.com/accounts/latest/reference/invite-team-members.html)
- [AWS: melhores práticas para o usuário raiz](https://docs.aws.amazon.com/IAM/latest/UserGuide/root-user-best-practices.html)
- [AWS: atualizar o e-mail do usuário raiz](https://docs.aws.amazon.com/accounts/latest/reference/manage-acct-update-root-user-email.html)
- [AWS IAM Identity Center: papéis criados pelo serviço](https://docs.aws.amazon.com/singlesignon/latest/userguide/identity-center-and-iam-roles.html)
- [AWS Organizations: melhores práticas para a conta de gerenciamento](https://docs.aws.amazon.com/organizations/latest/userguide/orgs_best-practices_mgmt-acct.html)
- [AWS Organizations: criar uma conta membro](https://docs.aws.amazon.com/organizations/latest/userguide/orgs_manage_accounts_create.html)
- [AWS Organizations: melhores práticas para múltiplas contas](https://docs.aws.amazon.com/organizations/latest/userguide/orgs_best-practices.html)
- [IAM Identity Center: tipos de instância e capacidades](https://docs.aws.amazon.com/singlesignon/latest/userguide/identity-center-instances.html)
- Inventário de leitura IAM da conta anterior e plano de reprodução: [`docs/architecture/aws-iam-inventory-conta-anterior.md`](../aws-iam-inventory-conta-anterior.md).
- [AWS Pricing Calculator](https://calculator.aws/)
- [AWS CodeBuild: runners hospedados para GitHub Actions](https://docs.aws.amazon.com/codebuild/latest/userguide/action-runner.html)
- [AWS CodeBuild: acesso à VPC](https://docs.aws.amazon.com/codebuild/latest/userguide/vpc-support.html)
- [Amazon EKS: Security Groups for Pods e limitações de instâncias](https://docs.aws.amazon.com/eks/latest/best-practices/sgpp.html)
- [Amazon EKS: NetworkPolicy VPC CNI em modo `strict`](https://docs.aws.amazon.com/eks/latest/userguide/cni-network-policy-configure.html)
- [Terraform: `terraform_remote_state`](https://developer.hashicorp.com/terraform/language/state/remote-state-data)
- [Terraform S3 backend: versioning e lock nativo](https://developer.hashicorp.com/terraform/language/backend/s3)
- [Amazon EKS: versões Kubernetes e ciclo de suporte](https://docs.aws.amazon.com/eks/latest/userguide/kubernetes-versions.html)
- [Amazon EKS: requisitos de rede e subnets](https://docs.aws.amazon.com/eks/latest/userguide/network-reqs.html)
- [API Gateway: domínio customizado Regional e DNS](https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-regional-api-custom-domain-create.html)
- [API Gateway REST: integração HTTPS privada com VPC Link V2](https://docs.aws.amazon.com/apigateway/latest/developerguide/private-integration.html)
- [Application Load Balancer: listener HTTPS com certificado ACM](https://docs.aws.amazon.com/elasticloadbalancing/latest/application/create-https-listener.html)
- [Application Load Balancer: certificados e correspondência de hostname](https://docs.aws.amazon.com/elasticloadbalancing/latest/application/https-listener-certificates.html)
- [CloudFront: requisitos de certificado TLS](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/cnames-and-https-requirements.html)
- [CloudFront: restringir acesso ao bucket S3 com OAC](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-restricting-access-to-s3.html)
- [AWS WAF com CloudFront: escopo global e associação](https://docs.aws.amazon.com/waf/latest/developerguide/cloudfront-features.html)
- [Secrets Manager: API `PutSecretValue`, versões e idempotência](https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_PutSecretValue.html)
- [Amazon EKS: Pod Identity e credenciais dos containers do Pod](https://docs.aws.amazon.com/eks/latest/userguide/pod-identities.html)
- [Kubernetes: volumes `emptyDir` em memória e contabilização](https://kubernetes.io/docs/concepts/storage/volumes/)
- [Kubernetes: swap e volumes tmpfs](https://kubernetes.io/docs/concepts/security/linux-security/)
- [RDS PostgreSQL: validar certificado e hostname TLS](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/UsingWithRDS.SSL.html)
- [AWS KMS: janela mínima para exclusão de chave](https://docs.aws.amazon.com/kms/latest/developerguide/deleting-keys.html)
- [AWS KMS: preços de armazenamento e uso de chaves](https://aws.amazon.com/kms/pricing/)

## Histórico

| Data | Alteração |
| --- | --- |
| 2026-10-23 | Registro inicial das decisões de arquitetura e tradeoffs aprovados para a infraestrutura da Fase 3. |
| 2026-10-23 | Decididos SSM Parameter Store como contrato entre repositórios e adiamento do RDS Proxy até haver métricas de carga e análise de custo. |
| 2026-10-23 | Decidido um segredo JSON com `DATABASE_URL` por identidade do banco. |
| 2026-10-23 | Decidido bootstrap idempotente de usuários/grants por Job efêmero dentro da VPC, sem provider PostgreSQL no Terraform. |
| 2026-10-23 | Atualizado o vínculo entre issues; criado o follow-up #113 para o delta de VPC Link, rotas de autenticação do cliente e WAF após o fechamento da #88. |
| 2026-10-25 | Inicialmente escolhida a conta Oficina Workload - 16SOAT (837155819003) para staging e produção, com gates separados; decisão suspensa após confirmação de que o ex-participante controla e-mail raiz, recuperação e conta de gerenciamento/faturamento. A conta atual fica fora da Fase 3 enquanto isso não for transferido ao grupo ativo. |
| 2026-10-25 | Aceito usar US East para staging e futura produção, com gate de latência/localização de dados em staging. `us-east-1` foi escolhida como região-base; comparar custo com `us-east-2` após definir o dimensionamento. |
| 2026-10-25 | Decidido usar duas Availability Zones em staging e produção; CIDRs e dimensionamento de IP permanecem pendentes de verificação de sobreposição e capacidade. |
| 2026-10-25 | Inspecionadas em modo somente leitura as VPCs da conta `837155819003` em `us-east-1` e `us-east-2`; ambas são default e usam `172.31.0.0/16`. A VPC informada tem IGW e rotas públicas, mas não foram encontrados ENIs, NAT, endpoints, peering, anexos a Transit Gateway ou Flow Logs; ela não atende à topologia privada sem remodelagem. |
| 2026-10-25 | Decidido não reutilizar as VPCs default na Fase 3 e usar uma VPC dedicada; CIDRs e dimensionamento de IP ficam pendentes até confirmar redes locais/VPN e a necessidade do EKS. |
| 2026-10-25 | Consultadas em modo somente de leitura as conexões de rede AWS em `us-east-1` e `us-east-2`; não foram encontrados VPNs, Customer/VPN Gateways, Transit Gateways, anexos a TGW nem VPC Peerings. As faixas da rede local ainda não foram validadas. |
| 2026-10-25 | Confirmado que o projeto é de aprendizado e não possui oficina/local físico; não há rede local a conectar e não é necessária VPN nesta fase. CIDRs continuam condicionados ao dimensionamento de IPs do EKS. |
| 2026-10-25 | Registrada referência preliminar de staging 24x7 em `us-east-1`: US$ 194,69/mês para EKS, NAT, ALB, dois nodes `t3.medium` e RDS `db.t4g.micro`, sem custos variáveis e itens excluídos descritos acima; não é autorização para provisionar. |
| 2026-10-25 | Gustavo definiu como prioridade manter o custo do projeto educacional o mais próximo possível do Free Tier; o cenário 24x7 não representa o modo de uso aprovado. Saldo/plano da conta ainda precisam ser verificados e a estratégia de staging de baixo custo continua em aberto. |
| 2026-10-25 | Aprovado staging AWS efêmero, usado somente durante integração/homologação e destruído ao final; desenvolvimento diário permanece local e produção fica sujeita a gate próprio. Recursos, duração e custo por sessão continuam pendentes. |
| 2026-10-25 | Registrado risco de governança porque a conta foi criada por participante que saiu do grupo. O uso da conta `837155819003` fica condicionado a confirmar controle do grupo ativo sobre usuário raiz, recuperação, MFA e organização/faturamento; se isso não puder ser transferido, usar conta governada pelos membros atuais. |
| 2026-10-25 | Gustavo confirmou que o ex-participante controla o e-mail raiz, todos os meios de recuperação e a conta de gerenciamento/faturamento. Recomendado não usar a conta `837155819003` na Fase 3 e criar/escolher conta substituta governada pelos membros ativos; seleção, responsável pelo faturamento, estrutura de organização e elegibilidade Free Tier permanecem pendentes. |
| 2026-10-25 | Gustavo decidiu criar uma conta AWS completamente nova com outro e-mail e configurar IAM do zero. Feito inventário IAM somente de leitura da conta anterior para apoiar a reprodução seletiva; registrado em `docs/architecture/aws-iam-inventory-conta-anterior.md`. A conta nova não foi criada e a conta antiga não foi alterada. |
| 2026-10-25 | Gustavo esclareceu que os requisitos atuais não pedem dois ambientes e aprovou um único staging AWS efêmero, com desenvolvimento local; produção e os requisitos exclusivos de produção ficam fora do escopo desta fase. Decisões anteriores de staging+produção foram atualizadas como futuras/deferidas. |
| 2026-10-25 | Aprovada uma única conta AWS standalone, sem Organization nesta fase. Humanos terão identidades individuais com MFA e credenciais temporárias; reavaliar SSO/Organizations se surgir necessidade de múltiplas contas. |
| 2026-10-25 | Gustavo definiu US$ 10/mês como gatilho para pausar novas sessões de staging, com alertas pretendidos em US$ 5, US$ 8 e US$ 10. AWS Budgets não garante um teto absoluto; teardown e revisão de custos continuam necessários. |
| 2026-10-25 | Gustavo confirmou que o grupo ativo não controla `autoshop.com` nem a zona DNS. Aprovado usar o hostname HTTPS padrão do API Gateway e HTTP no VPC Link até o ALB interno; domínio próprio, Route 53, ACM customizado e TLS nesse trecho ficam adiados. |
| 2026-10-25 | Gustavo informou que criou uma nova conta AWS e forneceu o ID `035611741563`. Registro feito com base na informação do usuário; plano/créditos, segurança da raiz, contatos, configuração standalone e autenticação ainda precisam de confirmação. |
| 2026-10-25 | Gustavo confirmou que o e-mail raiz da conta `035611741563` é controlado pelo grupo, que o MFA da raiz está ativo e que a conta está fora da Organization antiga. Plano/créditos, contatos alternativos, recuperação e status standalone continuam pendentes de confirmação. |
| 2026-10-25 | Atualizado o plano após aprovação de domínio próprio para API e frontend: `api.oficina-workshop.com.br` e `app.oficina-workshop.com.br`, com API Gateway Regional + CloudFront/S3 privado. O VPC Link V2 usa HTTPS verificado até o ALB interno; somente o trecho ALB–Pods permanece HTTP privado. Naquele momento, aquisição do domínio, controle da zona DNS, estimativa completa e aprovação para execução continuavam pendentes. |
| 2026-10-25 | Gustavo confirmou que a conta `035611741563` não pertence a nenhuma Organization (standalone) e informou plano Free, crédito de US$ 120 e 13 dias restantes conforme a tela consultada. A data exata do crédito e o encerramento do plano devem ser verificados separadamente; o alerta AWS Budgets de US$ 10 será configurado para custos unblended, sem contar créditos como redução do consumo. |
| 2026-10-25 | A captura do console esclareceu que o plano Free termina em 2026-11-06 ou quando os créditos forem esgotados, com US$ 120 ainda disponíveis. Gustavo informou que criou os budgets; validar os limites, a métrica de custo e a entrega dos alertas. Não fazer upgrade para Paid até estimar e aprovar o custo de continuidade. |
| 2026-10-25 | Gustavo confirmou a configuração dos budgets; a captura mostra alertas de custo real em US$ 5, US$ 8 e US$ 10 e ausência de ações automáticas. A validação da tela encerra essa pendência operacional. |
| 2026-10-25 | Gustavo confirmou que os contatos alternativos Billing, Security e Operations da conta `035611741563` já foram cadastrados. Recuperação da raiz e identidade IAM humana permanecem pendentes. |
| 2026-10-25 | Captura do console mostra IAM user existente na conta nova, em um grupo e com MFA virtual ativo. Não criar identidade duplicada; revisar policies anexadas, access keys e autenticação CLI antes de dar permissões adicionais. |
| 2026-10-25 | Gustavo informou que o IAM user existente herda `AdministratorAccess` pelo grupo `admin`. Registrar como estado atual, não como decisão de least privilege; ainda verificar access keys e preparar uma alternativa antes de reduzir as permissões atuais. |
| 2026-10-25 | Gustavo confirmou que o IAM user não possui access keys ativas. Como o usuário ainda herda `AdministratorAccess`, autenticação CLI fica pendente até preparar uma role de inspeção com leitura escopada. |
| 2026-10-25 | Gustavo optou por manter CLI administrativa para validações, priorizando o mínimo de configuração manual. A autorização para uso da conta nesta etapa limita-se a consultas; mutações e `terraform apply` continuam sujeitos a aprovação específica e ao ADR-0064. |
| 2026-10-25 | Instalado/encontrado AWS CLI v2.38.5 no Windows. A identidade do perfil `oficina-workload` foi consultada via STS e apontou para a conta antiga `837155819003`; nenhuma inspeção de recursos dessa conta foi feita depois da confirmação. Gustavo autorizou `aws login` para autenticar a nova conta. O callback local não funcionou na aba embutida; o fluxo foi reiniciado com `aws login --remote`. A tela da AWS mostrou a sessão ativa correta (`035611741563`, usuário `gustavo-ferreira`), e Gustavo autorizou disponibilizá-la temporariamente à CLI. A AWS exibiu um código de verificação; Gustavo deve inseri-lo diretamente no terminal, sem compartilhá-lo no chat. Confirmar `Account=035611741563` via STS antes de qualquer inspeção. |
| 2026-10-25 | Gustavo concluiu a autenticação remota no perfil `oficina-workload`. STS confirmou a conta `035611741563` e o usuário `gustavo-ferreira`; foi feita inspeção somente de leitura. Confirmados o grupo IAM `admin` com `AdministratorAccess`, MFA virtual e nenhuma access key. A conta possui somente VPCs default `172.31.0.0/16` nas regiões consultadas; os serviços EKS/RDS/NAT/ELBv2/Lambda/API Gateway consultados não retornaram recursos em `us-east-1`. Gustavo autorizou cadastrar via CLI o endereço de alertas que forneceu; uma primeira consulta de subscribers usou uma representação CLI que não identificou as notificações corretamente. A AWS rejeitou a tentativa de duplicar o threshold de US$ 5 e a consulta com JSON exato confirmou o endereço fornecido nos três thresholds de US$ 5/US$ 8/US$ 10. Nenhuma alteração nos budgets foi feita; o endereço não foi transcrito para este ADR. |
| 2026-10-25 | Gustavo confirmou que o grupo ativo possui acesso e recuperação documentados para a conta raiz `035611741563`; os dados concretos de recuperação não devem ser armazenados no repositório. |
| 2026-10-25 | AWS Free termina em 2026-11-06 ou quando os créditos acabarem. Gustavo decidiu não fazer upgrade para Paid e continuar local; uma retomada AWS dependerá de estimativa atualizada e aprovação explícita do upgrade e dos custos da sessão. |
| 2026-10-25 | Gustavo aprovou usar somente dados sintéticos no staging; haverá backup automático durante a sessão para validar recuperação, mas nenhum RDS, backup ou snapshot será retido após o teardown. |
| 2026-10-25 | Aprovado limite operacional de até 4 horas por sessão de staging, teardown no mesmo dia e sem recursos ligados durante a noite. Custo completo permanece sujeito ao Calculator e a uma nova aprovação antes do upgrade/execução. |
| 2026-10-25 | Gustavo será o único operador humano com acesso direto ao console/CLI AWS nesta fase; demais membros atuarão por PRs e pipelines com OIDC restrito. Não criar usuários adicionais nem compartilhar credenciais. |
| 2026-10-25 | Aprovado manter GitHub Actions como orquestrador e usar runner CodeBuild efêmero dentro da VPC somente para jobs que chamam a API Kubernetes; EKS fica privado e OIDC continua restrito. Incluir CodeBuild e sua saída de rede na estimativa de sessão. |
| 2026-10-25 | Revisão de `lambda-auth` confirmou que o módulo Terraform consome IDs existentes de subnets/SG; `k8s-infra` fornece os SGs de nodes e Lambda, e `database-infra` controla o SG do RDS. Como o sizing base usa `t3.medium`, usar SG dos nodes mais NetworkPolicy `strict`, sem Security Groups for Pods, que não suportam a família `t`. Credenciais serão renovadas a cada sessão, sem rotação automática dentro da janela de até 4 horas. |
| 2026-10-25 | Fechados os gates de desenho da Etapa 0: faixas CIDR exatas; EKS 1.37 e limites iniciais; sizing candidato de RDS; catálogo SSM com publicadores/leitores; backend S3 com lock nativo; TLS `verify-full`; MailHog e Redis efêmeros; `/docs` privado; rate limit inicial; domínio `oficina-workshop.com.br` com API `api.oficina-workshop.com.br` e frontend `app.oficina-workshop.com.br`; chave KMS de assinatura única por sessão e exclusão agendada no teardown. Aquisição informada; confirmação de titularidade/controle do grupo e acesso DNS, implementação, estimativa completa, validação do plan e aprovação de qualquer execução continuam pendentes. |
| 2026-10-25 | Revisão de escopo e custo (bloco "Revisão de escopo de 2026-10-25"): sessões com crédito Free, hml/prd por namespace, endpoint EKS com IAM sem CodeBuild, ALB no Terraform, nodes spot, três identidades de banco, notificação EventBridge→SNS+DLQ, New Relic, gatilho de pausa US$ 20. Criado o bucket de state e pedido aumento de quota de vCPU (on-demand e spot) para 16. |
| 2026-10-25 | Gustavo informou a compra de `oficina-workshop.com.br`. Hostnames definidos como `api.oficina-workshop.com.br` e `app.oficina-workshop.com.br`; falta identificar o provedor DNS e confirmar controle da zona pelo grupo. Nenhum registro, certificado ou recurso AWS foi criado. |
| 2026-10-25 | Gustavo confirmou que o DNS de `oficina-workshop.com.br` está no Registro.br e que ele tem acesso à zona. Controle por membro ativo confirmado; validar delegação e registros atuais antes de configurar ACM/CNAME. Nenhuma alteração DNS ou AWS foi feita. |
| 2026-10-26 | `k8s-infra` implementado e mergeado ([#12](https://github.com/Software-Architecture-Group-7-FIAP/k8s-infra/pull/12), [#13](https://github.com/Software-Architecture-Group-7-FIAP/k8s-infra/pull/13), [#14](https://github.com/Software-Architecture-Group-7-FIAP/k8s-infra/pull/14)). Sessão 1 executada de ponta a ponta: apply (bootstrap→foundation→platform) com 13/13 checks do smoke test aprovados, seguido de destroy sem órfãos. Nodes trocados de spot para On-Demand (#14): o plano Free da conta rejeita Spot em `t3.medium`/`t3a.medium`, confirmando na prática o fallback já previsto nesta decisão. Issues `k8s-infra#1`, `#2`, `#3`, `#4`, `#5`, `#7`, `#8`, `#9` fechadas com evidência da sessão; `k8s-infra#6` (calibração do HPA com carga representativa) permanece aberta — não demonstrada nesta sessão, fica para a etapa de carga/homologação. |
| 2026-10-27 | Conta confirmada como Paid com US$ 140 em créditos concedidos; quotas aprovadas em 16 vCPUs On-Demand e 32 Spot. `STAGING_ACTIVE=false`; sem EKS, NAT, RDS ou VPC da sessão ativos. CloudFront/S3 do Angular, domínio e WAF permanecem no escopo. Aprovado o bootstrap com init containers `aws-cli` + `postgres:16`, `PutSecretValue` e dados transitórios em tmpfs. |
