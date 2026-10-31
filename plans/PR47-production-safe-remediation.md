# PR 47 — Plano de correção para deploy seguro por ambiente

## Contexto de retomada

- **PR:** `#47 — T36 Condiguração do configMaps`
- **Branch:** `T36-setting-configMaps`
- **Head revisado:** `425dd0e7c29589c10a09d6461d8464281e89d16c`
- **Objetivo:** corrigir Kubernetes, segurança, migrations, configuração por
  ambiente e CI sem alterar o painel legado.
- **Decisão aprovada:** produção segura por padrão; diferenças de staging e
  desenvolvimento/local devem ser explícitas e controladas por ambiente.
- **Fora do escopo:** qualquer alteração em `frontend/legacy-panel` ou `/app/`.

Antes de implementar:

```powershell
git status --short --branch
git fetch origin
git switch T36-setting-configMaps
git pull --ff-only origin T36-setting-configMaps
git rev-parse HEAD
```

Preservar mudanças locais não relacionadas e não reescrever o histórico do PR.

---

## Objetivo e definição de pronto

Entregar manifests e automação que:

1. usem configuração segura de produção por padrão;
2. permitam overrides explícitos para local, development e staging;
3. nunca apliquem Secrets de exemplo;
4. usem imagem imutável identificada pela release;
5. executem migrations uma vez, antes do rollout da API;
6. falhem imediatamente quando uma etapa falhar;
7. exponham staging/produção somente por HTTPS;
8. validem readiness real do PostgreSQL e backend;
9. removam a exceção ECDSA do CI;
10. sejam cobertos por build, schema validation e smoke test em cluster efêmero.

O trabalho termina com CI verde, cobertura mínima de 80%, 100% nos novos
caminhos críticos e nenhum Secret, chave privada, kubeconfig ou ambiente real
versionado.

## Restrições

- Não alterar o painel legado.
- Não executar contra cluster ou banco compartilhado sem autorização.
- Não versionar `k8s/secrets.yaml`, `.env.*.local`, certificados privados ou
  credenciais.
- Não usar `latest` nem reutilizar a mesma tag entre builds.
- Não executar Alembic no startup das réplicas da API.
- Não mascarar saída ou código de retorno de build, migration ou deploy.
- Usar TDD para configuração, JWT e health checks.
- Preservar `plans/terraform/`; o overlay local deve ser compatível com esses
  planos.

---

## Arquitetura alvo

Usar Kustomize para separar base e ambientes:

```text
k8s/
  base/
    foundation/
      namespace.yaml
      configmap.yaml
      kustomization.yaml
    migration/
      migrate-job.yaml
      kustomization.yaml
    app/
      deployment.yaml
      service.yaml
      hpa.yaml
      kustomization.yaml
    ingress/
      ingress.yaml
      kustomization.yaml
  overlays/
    local/
      foundation/
      migration/
      app/
      ingress/
    staging/
      foundation/
      migration/
      app/
      ingress/
    production/
      foundation/
      migration/
      app/
      ingress/
  examples/
    secrets.example.env
  scripts/
    deploy.ps1
```

Decisões:

- `base` não contém PostgreSQL embutido nem credenciais.
- staging/produção esperam banco e Secret externos.
- local pode usar PostgreSQL no cluster e acesso por port-forward.
- exemplos ficam fora das árvores aplicadas.
- cada overlay define `APP_ENV`; não há detecção implícita.
- não existe um pacote raiz que aplique todas as fases de uma vez: setup e CI
  executam `foundation -> migration -> app -> ingress`, aguardando a condição
  de sucesso de cada fase antes de iniciar a seguinte.

| Configuração | Local/development | Staging | Production |
| --- | --- | --- | --- |
| `APP_ENV` | `development` | `staging` | `production` |
| URLs | localhost HTTP | HTTPS | HTTPS |
| CORS | origens locais explícitas | domínio staging | domínio produção |
| HSTS | desabilitado | habilitado | habilitado |
| SMTP | MailHog/sandbox | relay TLS | relay TLS |
| CPF externo | override explícito | obrigatório | obrigatório |
| Banco | PostgreSQL local | externo | externo/gerenciado |
| Ingress | opcional/port-forward | TLS obrigatório | TLS obrigatório |
| Imagem | SHA carregado no cluster | registry + SHA | registry + digest/SHA |

---

## Marcos e estimativa

| Marco | Esforço | Critério de sucesso |
| --- | ---: | --- |
| M1 — Estrutura por ambiente | 10–14h | fases dos três ambientes renderizam corretamente |
| M2 — Secrets, imagem e TLS | 15–25h | sem placeholder aplicado; HTTPS e imagem imutável |
| M3 — Migration e rollout | 11–17h | Job serializado e completo antes da API |
| M4 — Readiness e setup | 10–14h | deploy fail-fast e readiness real |
| M5 — CI e documentação | 9–15h | build, schema, cluster efêmero e smoke verdes |

**Estimativa das tarefas:** 51–79 horas. **Planejamento com contingência de
20%:** 61–95 horas. Os marcos podem se sobrepor quando as dependências permitirem;
por isso, suas faixas não devem ser somadas como duração de calendário.

---

## Fase 1 — Contratos e estrutura

### PR47-01 — Testar configurações por ambiente

- **Esforço:** 4–6h
- **Arquivos:** `tests/unit/test_config.py`, `src/config.py`
- **Dependências:** nenhuma

TDD obrigatório:

1. produção rejeita URLs HTTP;
2. produção exige `DATABASE_URL` não-placeholder;
3. produção exige SMTP autenticado e TLS;
4. produção exige token Invertexto;
5. development aceita MailHog/localhost somente de forma explícita;
6. JWT aceita somente o algoritmo decidido.

**Pronto:** testes falham antes, passam depois e cobrem 100% dos branches de
segurança alterados.

### PR47-02 — Criar base e overlays Kustomize

- **Esforço:** 6–8h
- **Arquivos:** `k8s/base/**`, `k8s/overlays/**`
- **Dependências:** PR47-01

Passos:

1. mover recursos compartilhados para `base`;
2. criar overlays local, staging e production;
3. mover PostgreSQL para local;
4. remover valores locais da produção;
5. preservar nomes/labels de Deployment, Service e HPA;
6. criar pacotes independentes para `foundation`, `migration`, `app` e
   `ingress`, sem agregador que aplique API e Job simultaneamente;
7. validar todas as fases com `kubectl kustomize`.

**Pronto:** produção não renderiza HTTP, localhost, MailHog, banco embutido ou
Secret de exemplo.

---

## Fase 2 — Secrets, JWT, imagem e TLS

### PR47-03 — Remover Secrets de exemplo do deploy

- **Esforço:** 3–5h
- **Dependências:** PR47-02

Passos:

1. mover o exemplo para `k8s/examples/`;
2. local cria Secret por `kubectl create secret generic --from-env-file` usando
   arquivo ignorado;
3. staging/produção exigem Secret previamente provisionado;
4. validar existência das chaves sem imprimir valores;
5. detectar placeholders e JWTs conhecidos no setup/CI;
6. usar uma única fonte para gerar `DATABASE_URL`, usuário e senha coerentes.

**Pronto:** nenhuma árvore Kustomize inclui Secret real ou de exemplo; ausência
ou placeholder bloqueia o rollout.

### PR47-04 — Remover a dependência ECDSA vulnerável

- **Esforço:** 4–8h
- **Arquivos:** dependências, adapter JWT e testes de auth
- **Dependências:** PR47-01

Abordagem:

1. substituir `python-jose` por `PyJWT` com HS256;
2. preservar o port atual de tokens;
3. testar algoritmo inesperado, expiração, assinatura inválida e `sub` ausente;
4. remover `ecdsa` do lock;
5. remover `--ignore-vuln PYSEC-2026-1325` da CI.

**Pronto:** `pip-audit` passa sem esse ignore e auth permanece compatível.

### PR47-05 — Usar imagem imutável

- **Esforço:** 4–6h
- **Dependências:** PR47-02

Passos:

1. tag = SHA do commit;
2. staging/produção usam registry e preferencialmente digest;
3. local carrega a imagem explicitamente no Kind/Docker Desktop;
4. injetar imagem por Kustomize;
5. API e Job usam o mesmo digest;
6. fixar UID/GID não-system na criação de `appuser` na imagem;
7. reutilizar os mesmos IDs no `securityContext` do Deployment e do Job;
8. validar `runAsNonRoot`, seccomp e remoção de capabilities no Kind;
9. nova build altera PodTemplate e dispara rollout.

**Pronto:** não há tag mutável nem risco de código e migration divergirem.

### PR47-06 — Exigir TLS fora do local

- **Esforço:** 4–6h
- **Dependências:** PR47-02

Passos:

1. adicionar `spec.tls` e Secret TLS;
2. habilitar redirect HTTPS;
3. habilitar HSTS somente com HTTPS;
4. usar URLs/CORS HTTPS em staging/produção;
5. documentar cert-manager ou certificado externo;
6. local usa port-forward ou Ingress local separado.

**Pronto:** produção não renderiza HTTP e HTTP é redirecionado para HTTPS.

---

## Fase 3 — Banco, migrations e readiness

### PR47-07 — Tornar PostgreSQL local realmente Ready

- **Esforço:** 3–5h
- **Dependências:** PR47-02, PR47-03

Passos:

1. manter `Recreate` ou usar StatefulSet de uma réplica;
2. adicionar startup/readiness/liveness com `pg_isready`;
3. adicionar resources e termination grace period;
4. impedir duas instâncias sobre o PVC;
5. aguardar readiness real.

**Pronto:** Job só inicia depois de `pg_isready`.

### PR47-08 — Corrigir e bloquear migrations

- **Esforço:** 4–6h
- **Dependências:** PR47-03, PR47-05, PR47-07

Passos:

1. definir UID/GID numéricos no Job;
2. aplicar Job somente após configuração, Secret e banco Ready;
3. usar o mesmo digest da API;
4. aguardar `condition=complete` com timeout;
5. mostrar logs sanitizados em falha;
6. impedir rollout da API se o Job falhar;
7. nomear Job por release ou recriá-lo com segurança;
8. serializar deploys por ambiente com `concurrency group` na CI/CD e bloqueio
   equivalente no script; se houver mais de um executor possível, adicionar
   Lease Kubernetes ou advisory lock no PostgreSQL;
9. no banco externo, executar preflight/retry limitado antes do Alembic, com
   timeout, `activeDeadlineSeconds` e `backoffLimit` finitos;
10. distinguir nos logs e no código de saída indisponibilidade do banco de erro
    da migration, sem expor a connection string;
11. manter API iniciando apenas Uvicorn.

**Pronto:** migration falha bloqueia deploy, somente um deploy por ambiente entra
na fase de migration e bancos externos indisponíveis falham dentro do timeout.

### PR47-09 — Separar liveness e readiness

- **Esforço:** 4–6h
- **Arquivos:** `src/main.py`, DB, testes e Deployment
- **Dependências:** PR47-01, PR47-08

TDD:

1. `/health/live` verifica somente o processo;
2. `/health/ready` faz `SELECT 1` com timeout curto;
3. readiness retorna 503 sem detalhes internos quando DB falha;
4. liveness não depende do DB;
5. probes usam os endpoints corretos.

**Pronto:** DB indisponível remove o Pod do tráfego sem criar restart loop.

---

## Fase 4 — Setup, CI e documentação

### PR47-10 — Reescrever o setup como fail-fast

- **Esforço:** 6–8h
- **Dependências:** PR47-02, PR47-03, PR47-05, PR47-08, PR47-09

O script recebe `-Environment local|staging|production` e:

1. valida ferramentas, kube-context e ambiente;
2. usa `$ErrorActionPreference = "Stop"`;
3. valida `$LASTEXITCODE` de processos externos;
4. renderiza/valida Kustomize;
5. aplica Namespace primeiro;
6. verifica Secret sem revelar valores;
7. adquire exclusão mútua do ambiente;
8. aplica a fase `foundation`;
9. aguarda PostgreSQL no local ou executa preflight limitado do banco externo;
10. aplica a fase `migration` e aguarda o Job;
11. aplica a fase `app` e aguarda rollout/readiness;
12. aplica a fase `ingress` quando necessário;
13. executa smoke test;
14. libera o lock do ambiente em bloco `finally`;
15. imprime sucesso somente no final.

Não descartar erros. Produção exige confirmação explícita e nunca cria Secret ou
certificado automaticamente.

**Pronto:** qualquer falha termina com código não zero e sem falso sucesso.

### PR47-11 — Ampliar CI/CD

- **Esforço:** 6–10h
- **Dependências:** PR47-04 a PR47-10

Adicionar:

1. `poetry check --lock`, pytest/cobertura, Bandit e `pip-audit` sem ECDSA ignore;
2. Docker build;
3. `docker compose config`;
4. renderização das quatro fases dos três overlays;
5. `kubeconform -strict` ou equivalente;
6. detector de placeholders, HTTP em produção e tag mutável;
7. cluster Kind efêmero e imagem carregada;
8. Secret temporário gerado no job;
9. PostgreSQL Ready → migration completa → API rollout;
10. exclusão mútua por ambiente e teste de dois deploys concorrentes;
11. banco externo indisponível falha dentro do timeout sem iniciar a API;
12. smoke em `/health/live`, `/health/ready` e `/docs`;
13. HPA quando Metrics Server estiver disponível.

**Pronto:** a CI reproduz os bloqueadores encontrados no review.

### PR47-12 — Atualizar documentação operacional

- **Esforço:** 3–5h
- **Dependências:** PR47-10, PR47-11

Documentar matriz de ambientes, Secrets, imagem, migration, TLS, rollback,
limpeza local e diagnóstico. Um membro novo deve conseguir executar local e
entender as dependências externas de staging/produção sem copiar credenciais.

---

## Dependências e paralelização

```text
PR47-01 -> PR47-02 -> PR47-03 -> PR47-07 -> PR47-08 -> PR47-09
                |          |                         |
                |          +-> PR47-05 --------------+
                +-> PR47-06                           |
PR47-01 -> PR47-04                                  PR47-10
PR47-04 + PR47-06 + PR47-10 -> PR47-11 -> PR47-12
```

Após PR47-02, PR47-04, PR47-05, PR47-06 e PR47-07 podem ser paralelos. O caminho
crítico é Secrets → banco Ready → migration → readiness → setup → CI.

## Estratégia de commits

1. `test: define environment security contracts`
2. `refactor(k8s): split base and environment overlays`
3. `fix(k8s): prevent example secrets from deployment`
4. `refactor(auth): replace python-jose with pyjwt`
5. `fix(k8s): use immutable release images`
6. `fix(k8s): require tls outside local environment`
7. `fix(k8s): gate rollout on database migrations`
8. `feat: add database-aware readiness endpoint`
9. `fix(devops): make environment deployment fail fast`
10. `ci: validate container and kubernetes rollout`
11. `docs: document environment deployment workflow`

Não usar `git add .`. Revisar cada diff. Não fazer push sem autorização
explícita.

---

## Validação final obrigatória

```powershell
poetry check --lock
poetry run pytest --cov=src --cov-report=term-missing
poetry run bandit -r src -ll
poetry run pip-audit --skip-editable
docker build -t auto-shop-system:$env:GIT_SHA .
docker compose --env-file .env.example config
kubectl kustomize k8s/overlays/local/foundation
kubectl kustomize k8s/overlays/local/migration
kubectl kustomize k8s/overlays/local/app
kubectl kustomize k8s/overlays/local/ingress
# Repetir as quatro fases para staging e production.
git diff --check
git status --short
```

Executar também `kubeconform -strict`, cluster efêmero, migration bloqueante,
rollout e smoke tests. Critérios:

- `/health/live` responde com processo saudável;
- `/health/ready` só responde 200 com DB utilizável;
- migration falha impede rollout;
- somente um deploy por ambiente pode executar migrations por vez;
- banco externo indisponível encerra a fase dentro do timeout configurado;
- produção não contém HTTP, localhost, Secret de exemplo ou tag mutável;
- logs e artefatos não contêm credenciais;
- cobertura global >= 80% e 100% nos novos validadores, JWT e health checks.

---

## Matriz de fechamento dos achados

| Achado | Critério para fechar |
| --- | --- |
| Secret de exemplo aplicado | exemplo fora da árvore; Secret real obrigatório |
| Credenciais DB divergentes | fonte única produz URL e credenciais coerentes |
| Job bloqueado por usuário | UID/GID fixos na imagem/manifests; Job inicia no cluster |
| API antes da migration | fases separadas; rollout só após Job completo |
| Migrations concorrentes | lock por ambiente e teste de concorrência |
| Banco externo indisponível | retry limitado, deadline e diagnóstico sanitizado |
| Setup mascara falhas | código não zero e sem falso sucesso |
| SMTP incompleto | username/password/TLS obrigatórios em produção |
| URL frontend incorreta | frontend público correto por ambiente |
| Ingress HTTP | TLS e redirect em staging/produção |
| Tag reutilizada | SHA/digest altera PodTemplate |
| PostgreSQL não Ready | `pg_isready` e wait real |
| Readiness superficial | DB check e 503 em falha |
| ECDSA ignorada | dependência removida; audit sem ignore |
| CI superficial | build, schema, Kind, migration e smoke no pipeline |

---

## Riscos e mitigação

| Risco | Impacto | Probabilidade | Mitigação |
| --- | --- | --- | --- |
| Reorganização quebra planos Terraform locais | Alto | Médio | preservar nomes e validar overlays com `K8S-*` |
| Migration irreversível falha | Alto | Médio | backup, Job bloqueante e rollback documentado |
| Secret vaza na CI | Alto | Baixo | env-file, masking e nunca usar `get secret -o yaml` |
| TLS indisponível | Alto | Médio | preflight e bloqueio de produção |
| Cluster não encontra imagem | Médio | Médio | load explícito e verificação de digest |
| Readiness sobrecarrega DB | Médio | Baixo | query simples, timeout e frequência controlada |
| Troca JWT quebra sessões | Alto | Médio | testes de compatibilidade e rollout coordenado |
| Escopo invade painel legado | Médio | Baixo | exclusão explícita e revisão por commit |

---

## Handoff para o próximo contexto

O próximo executor deve:

1. ler este documento inteiro;
2. confirmar o head remoto e revisar commits posteriores a `425dd0e7`;
3. iniciar por PR47-01 seguindo TDD;
4. não modificar o painel legado;
5. manter produção segura por padrão e local como overlay explícito;
6. atualizar este plano apenas se uma decisão mudar materialmente;
7. ao final, informar commits, validações, limitações e bloqueadores de merge.
