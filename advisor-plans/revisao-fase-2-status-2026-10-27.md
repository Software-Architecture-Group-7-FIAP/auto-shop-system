# Revisão de status — Fase 2 e estado geral do projeto

**Data:** 2026-10-27 · **Escopo:** revisão do que foi feito até agora, achados de segurança/documentação no `database-infra`, e próximos passos.

## Resumo em uma frase

A Fase 1 (`k8s-infra`) está pronta e provada em sessão real. A Fase 2 (`database-infra`) tem commit local `b80a7d7` na branch de feature, sem push ou CI. O bootstrap que estava stub bloqueado foi implementado, mas ainda aguarda validação runtime em staging.

## O que foi feito

| Etapa | Resultado |
|---|---|
| Revisão de arquitetura e custo | Achados A1–A17, plano de correção e artefato HTML com diagramas |
| Limpeza de issues e ADR | 15 issues reescritas, 4 criadas (#117–#120), ADR-0071 revisado, bucket de state e pedido de quota |
| Fase 1 (`k8s-infra`) | PRs #12, #13 e #14 mergeados. A Sessão 1 aplicou tudo e passou 13/13 no smoke test. O destroy foi limpo, sem órfãos. Issues #1–#5 e #7–#9 fechadas |
| Fase 2 | O checkout `feat/database-infra-phase-2` contém o commit local `b80a7d7`. Bootstrap e correções #2/#4–#8 estão implementados. Testes Terraform, shell, PostgreSQL 16 e Checkov passaram localmente; CI e validação em EKS continuam pendentes |

**AWS agora:** nada cobrável rodando (sem EKS, NAT, RDS ou VPC), só as 8 roles IAM persistentes. As trust policies vivas batem com o desenho, sem nada amplo demais. Mudou em relação à documentação: o plano da conta é **PAID**, com **US$ 140** de crédito. As quotas de vCPU foram aprovadas (16 on-demand, 32 spot). O gasto aparece como US$ 0, mas o Cost Explorer tem atraso. `STAGING_ACTIVE=false` e não há secrets nos repositórios.

## `database-infra`: achados

Os itens marcados com ✔ foram reproduzidos ou lidos diretamente no código. Os demais vieram do revisor de segurança, parte por inferência.

| # | Sev. | Achado |
|---|---|---|
| 1 | **Crítico** ✔ | O stub fail-closed foi substituído por um Job local com AWS CLI, resolver Python/`asm-exec`, `postgres:16`, `PutSecretValue` e volumes temporários em memória. A execução em EKS continua pendente de uma sessão staging autorizada e da validação de conectividade do resolver |
| 2 | **Crítico** ✔ | Corrigido localmente: `plan-guard.sh` reconstrói endereços a partir de `configuration.module_calls` e normaliza índices. O fixture usa a estrutura real do JSON do Terraform; os contratos locais passaram e o CI continua pendente |
| 3 | Alto ✔ | O Checkov 2.0.930 do workflow agora reporta 54 verificações aprovadas, 0 falhas e 10 skips inline com justificativas. `auto_minor_version_upgrade` foi habilitado; os skips restantes documentam decisões de staging, logs com risco de PII, chave KMS gerenciada pela AWS, parâmetros SSM não secretos e associação de SG entre módulos |
| 4 | Alto ✔ | Corrigido localmente: o teardown continua quando o parâmetro/cluster upstream está realmente ausente, pula a limpeza Kubernetes e usa o state armazenado (`-refresh=false`) apenas nesse caso. Falhas de acesso continuam bloqueando o destroy |
| 5 | Médio ✔ | Corrigido localmente: bootstrap não revoga privilégios de tabela da role Lambda; a fase `10-lambda-grants.sql` continua sendo responsável por reconciliar os grants depois das migrations |
| 6 | Médio | Corrigido localmente: o runtime gera verificador SCRAM-SHA-256, entrega o SQL por arquivo privado em memória e não passa a senha em texto nos argumentos de `psql`. A validação real do fluxo ainda depende da sessão staging |
| 7 | Médio ✔ | Corrigido localmente: CI instala `ripgrep` nos jobs que executam os contratos. Ainda restam limitações de alguns testes e a suíte SQL usa uma instância sintética como superusuário; não foram alteradas nesta rodada |
| 8 | Baixo | Corrigida localmente a trust do Pod Identity para fixar namespace e service account. Permanecem a cobertura incompleta da auto-checagem SQL, a validação de janela de recuperação no `orphans.sh` e checksum do download do kcov |
| 9 | Alto ✔ | A varredura local do Checkov 2.0.930 identificou os recursos e os skips inline agora incluem os IDs e justificativas; não há falhas restantes na análise Terraform |

**Verificado correto:** RDS (criptografia, backups, teardown, sem senha em argumento), secrets com `recovery_window=0`, cron das 01:30 (evita a corrida com o destroy das 02:00 do `k8s-infra`), as 10 chaves SSM da issue #5, e a engine `16.15` (existe e é encomendável em `db.t4g.micro` gp3 na conta).

## Outros riscos de segurança e governança

- **`lambda-auth` sem proteção de branch** em `main` e `develop`. É exigência explícita do PDF e da issue #91.
- `k8s-infra/main` não exige nenhum check obrigatório, então dá para mergear com CI vermelho.
- `auto-shop-system` tem `enforce_admins=false`. Os environments `staging` não têm reviewers configurados. `auto-shop-system` e `lambda-auth` **não têm nenhum Environment** criado (as roles de deploy deles ficam inassumíveis por ora — o que atualmente é seguro, mas bloqueia deploy quando chegar a vez).
- Endurecimento pendente: adicionar `rds:DownloadDBLogFilePortion` ao deny do papel de plan (inferência de que `ReadOnlyAccess` o inclui, não confirmado).
- A conta agora é **PAID**, então há cobrança real quando o crédito acabar. Os budgets (US$ 10/5/1) só alertam, não bloqueiam; o "gatilho de US$ 20" citado no ADR-0071 não existe de fato configurado na AWS.

## Documentação — estado após esta revisão

- **ADR-0071, planos e Blueprint:** copiados para a branch `docs/fase2-status-2026-10-27`. ADR e Blueprint registram a conta Paid, saldo de crédito desconhecido, quotas 16/32, SSM atual, três identidades, endpoint EKS público/privado sem CodeBuild e escopo CloudFront/domínio/WAF. O custo completo segue pendente.
- **Planos de execução anteriores:** os guias de Fase 1 e Fase 3 agora trazem avisos de estado atual e apontam para o ADR/status como fontes normativas. Trechos antigos permanecem como histórico da auditoria; não devem ser usados como instruções atuais quando houver divergência.
- **README do `k8s-infra`:** a cópia local ainda cita quota "5, pedido aberto" e a nota de nodes "efetivamente imutáveis" baseada em 5 vCPU. Esse repositório externo ainda precisa ser atualizado.
- **Ausentes:** `docs/rfc/` e `docs/adr/` de implementação (o PDF do Tech Challenge exige RFCs e ADRs explicitamente). O README principal do `auto-shop-system` não descreve a arquitetura da Fase 3, e os diagramas `fase2-architecture.*` são da fase anterior.

## Issues e PRs

- **Abertas com razão válida:** `k8s-infra#6` (HPA, falta teste de carga), `database-infra#1–#5`, `#113` e `#115–#120`, `#85`, `#87`, `#68`, `#92–#94`.
- **Candidata a fechar:** `lambda-auth#3` — preparação de IaC já mergeada nos PRs #6, #8 e #10.
- **`#91`, `#89`, `#90`:** parciais, ver os gaps de proteção de branch listados acima.
- **`#98` (tracker integrado):** precisa de atualização para refletir o estado real das outras issues.
- **PRs travados, precisando de ação:**
  - `auto-shop-system#112` (identidade do cliente) está **aprovado, com CI verde, e sem merge**.
  - `lambda-auth#11` (rotação de JWKS) está verde, sem review e sem merge.
  - `auto-shop-system#110` (logs JSON) tem changes requested e o check `test-and-security` vermelho.
  - `auto-shop-system#114` (docs) está com `test-and-security` vermelho.

## Próximos passos

1. **Preservar o trabalho:** branch local `docs/fase2-status-2026-10-27` criada a partir de `origin/develop`; ADR, plans e Blueprint foram copiados e revisados nessa branch. O `database-infra` contém o commit local `b80a7d7` em `feat/database-infra-phase-2`. O remoto está sem refs e sem branch padrão, então o push aguarda a inicialização de uma base.
2. **Destravar o `database-infra`:** bootstrap (#1), #2 e #4–#8 estão implementados. #3 foi validado no Checkov 2.0.930 (54 aprovados, 0 falhas, 10 skips inline justificados). CI, revisão, PR e branch protection continuam pendentes; o preflight de staging depende dos cinco parâmetros upstream de SSM.
3. **Merges e proteções pendentes:** mergear `#112` e `lambda-auth#11`. Adicionar proteção de branch ao `lambda-auth`. Exigir checks obrigatórios no `k8s-infra/main`.
4. **Sessão 2 (com autorização explícita por apply):** `k8s-infra` → `database-infra` → bootstrap → smoke → grants → destroy.
5. **Resto da Fase 3, ainda não iniciado:** deploy do `lambda-auth` com `verify-full`; migrations e digest (#115/#116) e o CD hml/prd (#90); API Gateway com VPC Link, WAF e domínio (#113); EventBridge → SNS (#117); session-up/down (#118); New Relic (#92–#94, #110); OpenAPI/Postman (#119); RFCs, ADRs, READMEs e diagramas (#95/#120/#114); HPA (`k8s-infra#6`); homologação (#68) e vídeo de demonstração.
6. **Recalcular custos antes de uma sessão AWS:** incluir CloudFront/S3, domínio, ACM e WAF regional + WAF CloudFront; confirmar o saldo de créditos e revisar o tempo de teardown. Budgets atuais são alertas, não limites de gasto.

## Decisões registradas em 2026-10-27

- **Bootstrap do banco:** desenho implementado localmente com AWS CLI, `postgres:16`, `PutSecretValue` e arquivos sensíveis/temporários em tmpfs. Um init Python adicional executa o `asm-exec` aprovado. A execução real aguarda validação em staging.
- **Branch de documentação:** a branch local `docs/fase2-status-2026-10-27`, criada a partir de `develop`, mantém ADR, plans e Blueprint separados da branch da Pessoa 1.
- **Escopo:** não reabrir o corte de 28/10. CloudFront do Angular, domínio próprio e WAF permanecem no escopo.


## Estado do bootstrap implementado localmente

- A fase `bootstrap` usa AWS CLI para credenciais temporárias e metadados, `asm-exec` para resolver o master e versões atuais das quatro credenciais de aplicação, SQL em `postgres:16` para criar bancos/roles e `PutSecretValue` apenas para payloads ausentes ou desatualizados. Em retries, os valores atuais são reutilizados e os roles são reconciliados com eles.
- A fase `grants` aplica os privilégios Lambda depois das migrations. A fase `smoke` testa `verify-full`, hostname, autenticação, privilégios mínimos e isolamento entre bancos. O workflow executa smoke inicial depois do bootstrap e smoke completo depois de grants.
- Um init Python foi incluído porque o `asm-exec` aprovado é um wrapper Python. Os contêineres AWS CLI e `postgres:16` do desenho permanecem.
- Senhas, credenciais temporárias, `pgpass`, verificadores SCRAM, payloads, certificado CA e temporários do Job ficam em `emptyDir.medium: Memory`; temporários do orquestrador local ficam em `/dev/shm`. ConfigMaps guardam apenas código e metadados não secretos.
- O runtime depende de saída HTTPS para o backend do `asm-exec` (AWS MCP ou SMA configurado) e para o bundle de CA do RDS. Essa conectividade e o Pod Identity ainda não foram validados no EKS. Foram executados `terraform fmt`, `validate` e 3 testes do módulo RDS; ShellCheck; contratos shell/workflow e bootstrap/grants em PostgreSQL 16; Checkov 2.0.930 (54 aprovados, 0 falhas, 10 skips inline justificados). A medição kcov ficou em 0% no container local, inclusive em um script mínimo, então a cobertura medida continua pendente no CI. O preflight AWS somente de leitura encontrou ausentes os cinco parâmetros de rede/EKS e o plano de staging foi pulado. Nenhum apply foi executado.
- O corte definido permanece: CloudFront do Angular, domínio próprio e WAF continuam no escopo. A documentação continua isolada na branch `docs/fase2-status-2026-10-27`.

---

*A documentação segue na branch separada `docs/fase2-status-2026-10-27`. O commit `b80a7d7` da implementação `database-infra` é local e ainda não foi enviado; o remoto está vazio, sem refs/default branch, então CI e PR não foram iniciados. Os testes Terraform, shell, PostgreSQL 16 e Checkov passaram localmente; kcov e runtime em EKS continuam pendentes. O preflight AWS foi somente de leitura e encontrou os cinco parâmetros upstream ausentes. Nenhum apply ou leitura de valor de secret foi feito.*
