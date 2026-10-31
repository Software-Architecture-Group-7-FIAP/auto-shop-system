# Fase 3 — Pessoa 3: observabilidade, notificações e entrega

## 1. Identificação e validade

| Campo | Registro |
| --- | --- |
| Tipo | Documento de execução e acompanhamento; decisões herdadas dos ADRs existentes. |
| Responsável atual | Outro desenvolvedor da dupla; nome a registrar pela equipe. |
| Colaborador e revisor | Gustavo, responsável pelas frentes originais das Pessoas 1 e 2. |
| Data-base | 22/10/2026, America/Sao_Paulo. |
| Estado | Planejado parcialmente e com instrumentação em PR; aceite operacional pendente. |
| Rastreabilidade | Issues #92–#95, PR #110, contrato de evento #67 e homologação #68/#87. |

Este documento deriva do [relatório consolidado](relatorio-fase-3-status-e-divisao-2-devs.md), sem uma nova consulta aos repositórios ou à AWS. Os estados abaixo representam o retrato daquela análise e devem ser atualizados com evidências de execução.

Documentos relacionados: [Pessoa 1 — identidade e integração](fase-3-pessoa-1-identidade-e-integracao.md), [Pessoa 2 — plataforma e CI/CD](fase-3-pessoa-2-plataforma-e-cicd.md) e [divisão original](../docs/contexts/tasks/fase-3-divisao-3-pessoas.md).

## 2. Contexto e resultado esperado

A aplicação já implementa autenticação de cliente, consulta da própria OS e produção de evento de falha. A plataforma cloud ainda precisa ser integrada. A Pessoa 3 transforma esses componentes em uma operação investigável e demonstrável: uma requisição deve ser correlacionada entre componentes, falhas devem chegar ao canal de notificação e os dados devem sustentar dashboards e evidências da entrega.

O resultado esperado é observar o caminho Gateway → Lambda/API → banco/eventos → consumidor, demonstrar indicadores técnicos e de negócio e entregar documentação, vídeo e PDF coerentes com o ambiente efetivamente implantado.

Ausência de evidência nesta análise significa entrega não comprovada. Não autoriza afirmar que nenhum recurso exista fora dos repositórios consultados.

## 3. Escopo, propriedade e limites

**Responsabilidade final da Pessoa 3:** padronizar e instrumentar logs, métricas e traces; integrar a ferramenta de observabilidade; construir dashboards e alertas; implementar o consumidor serverless de notificações; consolidar documentação arquitetural, READMEs, evidências, vídeo e PDF.

**Responsabilidade de Gustavo/Pessoa 1:** regras de negócio, JWT e autorização, contrato e produtor do evento, execução funcional da homologação e revisão de instrumentação nos casos de uso.

**Responsabilidade de Gustavo/Pessoa 2:** EKS/RDS/rede, IAM, secrets, recursos de coleta e mensageria, targets/DLQ/permissões, pipelines e deploy. A Pessoa 3 fornece os requisitos desses recursos e valida a operação junto com ele.

Mudanças de instrumentação na aplicação e Lambda devem ser entregues por PR com revisão cruzada. A responsabilidade documental não transfere a propriedade de schema/migrations, regras de autenticação ou infraestrutura para a Pessoa 3.

## 4. Estado comprovado e pendências

| Entrega | Estado na data-base | Evidência / limite |
| --- | --- | --- |
| #92 — ferramenta de observabilidade | Pendente de evidência | Integração completa de app, Lambda, cluster e banco não comprovada. |
| #93 — logs JSON, correlação e traces | Parcial | [PR #110](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/pull/110) aberto; logs JSON/correlação da API preparados, traces e métricas posteriores. |
| CI do PR #110 | Aprovado | [Run 39777031353](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/actions/runs/39777031353); não comprova integração ou coleta em cloud. |
| Correlação no produtor de eventos | Implementada no escopo funcional | #67 utiliza UUID técnico em `request_id`; publicação best-effort. |
| Correlação na Lambda de cliente | Pendente | Adapter HTTP local auditado não preservava headers/request ID para investigação ponta a ponta. |
| #94 — dashboards e alertas | Pendente de evidência | Painéis publicados e alertas testados não comprovados. |
| Consumidor de falha de OS | Não localizado | Produtor existente não substitui consumidor, canal, deduplicação e tratamento de falhas. |
| #95 — documentação | Parcial | Arquitetura anterior, ER e ADRs funcionais existem; conjunto final da Fase 3 incompleto. |
| Vídeo e PDF final | Não comprovados | Faltam evidências consolidadas e pacote de entrega verificável. |

O PR #110 deve ser revisado contra a `develop` vigente antes de integrar. Não tratar falhas históricas de sua branch como estado atual, nem declarar #93 concluída apenas pela entrega de logs da API.

## 5. Decisões herdadas e definições em aberto

As decisões funcionais de referência estão no [ADR de autenticação](../docs/architecture/decisions/ADR-0064-autenticacao-cliente-cpf-jwt.md) e no [ADR de consulta/evento](../docs/architecture/decisions/ADR-0066-0067-os-cliente-e-evento-de-falha.md).

Decisões já registradas que esta frente deve respeitar:

- JWT de cliente RS256/KMS, sem dados pessoais nas claims, validado pela API; telemetria não deve registrar o token.
- Evento `ServiceOrderProcessingFailed` v1 para falhas inesperadas ao enfileirar, iniciar ou finalizar OS; erros de domínio esperados não geram o evento.
- Publicação best-effort sem outbox: a falha da publicação preserva a exceção original e pode perder a notificação.
- Correlação técnica por UUID: `X-Correlation-ID` tem precedência sobre `X-Request-ID`; valor ausente ou inválido é substituído por UUID.
- Homologação usa dados sintéticos e evidências sanitizadas; não há aceite de operação cloud apenas por testes com fakes.

Definições ainda necessárias, sem aprovação presumida neste documento: ferramenta de observabilidade, canal de notificação, retenção, amostragem de traces, limites de volume/custo, metas operacionais e thresholds de alerta. Registrar alternativa escolhida, justificativa, custo e responsáveis em RFC/ADR conforme a natureza da decisão.

## 6. Contrato de telemetria e correlação

### 6.1 Logs estruturados

Adotar JSON com campos mínimos `timestamp`, `level`, `service`, `environment`, `version` e identificador de correlação. O PR #110 já prepara parte desse formato; conferir lacunas de versão e consistência entre serviços antes de fechar o contrato.

Usar nomes de evento/código estáveis para diagnóstico. `request_id` no evento de domínio deve permitir localizar a correlação correspondente nos logs. Identificadores `event_id` e `service_order_id` podem aparecer como dados técnicos necessários ao diagnóstico.

CPF/CNPJ, nome, contato, credenciais, segredos, cookies, JWT completo, payload de login e descrições sensíveis de exceções não entram nos logs ou notificações. Sanitizar também bibliotecas, access logs, rastreamento de SQL e atributos de traces. Redação na saída é defesa adicional; evitar coletar o dado na origem.

### 6.2 Propagação e validação

| Fronteira | Comportamento a entregar | Evidência de aceite |
| --- | --- | --- |
| Gateway → Lambda/API | Transportar identificador acordado e validar a convenção UUID. | Requisição sintética encontrada com a mesma correlação nos dois componentes. |
| Lambda → dependências | Preservar contexto ao consultar banco/assinar token sem registrar entradas sensíveis. | Falha simulada/real controlada investigável por correlação e categoria técnica. |
| API → caso de uso/evento | Manter o UUID em logs e `request_id`. | Falha de OS e evento v1 localizados pelo mesmo contexto. |
| EventBridge → consumidor | Preservar `event_id`, `request_id` e `service_order_id`. | Consumo, resultado e notificação vinculados aos identificadores. |
| Logs → traces | Vincular trace/span à correlação técnica quando suportado. | Navegação entre requisição, logs e trace sem PII. |

O contexto de tracing não substitui automaticamente o UUID contratual. Gateway e aplicação devem ser testados juntos, pois o identificador nativo do Gateway pode seguir formato diferente.

### 6.3 Instrumentação por componente

| Componente | Dados a coletar | Restrições / dependência |
| --- | --- | --- |
| API FastAPI | Taxa, duração, status HTTP, erros, dependências e transições de OS. | Identificar por template de rota; evitar cardinalidade por cliente/OS em labels de métricas. |
| Lambda de cliente | Invocações, erros, duração, cold start, timeout e throttling. | Correlação no adapter/handler; não capturar CPF/body/token. |
| Gateway | Volume, latência, códigos, rejeições e throttling. | Coleta efetiva depende das rotas cloud e permissões da Pessoa 2. |
| Kubernetes | CPU/memória, réplicas/HPA, reinícios, readiness/liveness e pods indisponíveis. | Coletor e permissões com menor privilégio; cluster de staging disponível. |
| PostgreSQL gerenciado | Saúde, conexões e falhas/latência de acesso quando disponíveis. | Não exportar parâmetros SQL, documentos pessoais ou credenciais. |
| Produtor/consumidor | Publicação/consumo, erros, retries, duplicados e DLQ. | Falha de publicação não pode depender exclusivamente do próprio bus para ser observada. |

## 7. Métricas, dashboards e alertas

Cada painel deve registrar fonte, consulta/cálculo, período, unidade, ambiente, filtros e responsável. Distinguir ausência de tráfego de indisponibilidade e ausência de dados de valor zero.

| Painel obrigatório | Fonte e unidade propostas para validação | Critério de aceite |
| --- | --- | --- |
| 1. Volume diário de OS | Evento/métrica de criação ou consulta agregada autorizada; OS/dia. | Contagem conferida com conjunto sintético conhecido e fuso/período explícitos. |
| 2. Tempo médio por status | Histórico/transições de Diagnóstico, Execução e Finalização; segundos/minutos. | Fórmula define entrada/saída e OS ainda abertas; resultado conferido com tempos conhecidos. |
| 3. Falhas nas integrações | Métricas/logs categorizados por dependência; contagem e taxa. | Falha controlada aparece na integração correta, sem dados pessoais. |
| 4. Latência/disponibilidade da API | Histogramas HTTP e verificações sintéticas; milissegundos e percentual. | Distribuição/percentis e janela explícitos; sucesso e indisponibilidade controlados visíveis. |
| 5. Recursos Kubernetes | Coletor do cluster e HPA; CPU, memória e réplicas com unidades explícitas. | Dados do namespace/workload corretos, escalabilidade e reinícios observáveis. |
| 6. Healthchecks e uptime | Readiness/liveness e checks externos; estado e percentual por período. | Diferencia processo vivo, pronto para tráfego e endpoint acessível externamente. |
| 7. Falhas no processamento de OS | Evento v1 e métricas de produtor/consumidor; falhas/intervalo. | Evento, consumo e resultado relacionados; perda de publicação tem sinal próprio. |
| 8. Investigação por correlação | Logs/traces indexados por UUID e IDs técnicos; linha temporal. | Uma falha sintética pode ser seguida até consumidor/notificação. |

A existência de um evento de falha não fornece, por si só, volume diário de OS ou tempo por status. Identificar a fonte de negócio existente e adicionar instrumentação com Gustavo se a informação necessária não estiver disponível.

Definir alertas para indisponibilidade, erro/latência, recursos/reinícios, Lambda, banco, publicação/consumo e DLQ. A dupla deve aprovar thresholds a partir de metas e medições de staging; este documento não inventa valores. Para cada alerta, registrar janela, severidade, destino, deduplicação, condição de recuperação e procedimento de atendimento.

## 8. Consumidor serverless de notificações

### 8.1 Contrato de entrada e comportamento

O evento v1 contém `event_id`, `event_type`, `event_version`, `occurred_at`, `request_id`, `service_order_id` e `severity`. O tipo esperado é `ServiceOrderProcessingFailed`. Validar envelope do transporte e conteúdo antes de notificar; não pressupor que todo evento recebido seja confiável ou compatível.

Fluxo esperado: receber → validar contrato/versão → verificar deduplicação → enviar ao canal acordado → registrar resultado técnico. O consumidor não deve consultar dados pessoais para enriquecer o aviso sem requisito explícito e revisão do contrato.

Deduplicar por `event_id` com mecanismo persistente compatível com retries e concorrência. Definir o momento de marcar sucesso: marcar antes do envio pode perder aviso; marcar somente depois pode repetir aviso quando o provedor confirmou e a resposta se perdeu. Documentar essa limitação e usar idempotência do provedor quando disponível.

Versão desconhecida e payload inválido devem ter tratamento explícito, observável e seguro, com quarentena/DLQ conforme topologia definida. Não entrar em retry infinito nem descartar silenciosamente. A Pessoa 2 provisiona destino, permissões, política de retry/DLQ e armazenamento necessário; a Pessoa 3 implementa o comportamento e os testes.

### 8.2 Testes obrigatórios e evidências

| Cenário | Resultado esperado |
| --- | --- |
| Evento v1 válido | Uma notificação com identificadores técnicos e sem PII. |
| Mesmo `event_id` repetido ou concorrente | Deduplicação conforme política; ausência de efeitos duplicados evitáveis. |
| Versão desconhecida / campos inválidos | Rejeição/quarentena observável, sem envio inadequado e sem loop infinito. |
| Timeout/falha temporária do provedor | Retry limitado e rastreável; sem segredo/detalhe sensível na saída. |
| Falha persistente | Mensagem chega à DLQ/tratamento acordado e dispara alarme. |
| Reprocessamento autorizado | Procedimento documentado preserva deduplicação e correlação. |

Testes unitários/contratuais usam doubles; testes cloud e notificações reais ocorrem no staging acordado. Guardar resultados e timestamps sanitizados, sem copiar dados de autenticação.

## 9. Backlog e ordem de execução

| Ordem | Atividade | Dependência | Saída / aceite |
| --- | --- | --- | --- |
| P3-01 | Revisar e integrar fatia de logs do PR #110. | Branch atual e revisão de Gustavo. | Testes aprovados e formato JSON/correlação integrado sem regressão. |
| P3-02 | Definir ferramenta, contrato de logs/traces, retenção e custos. | Decisão conjunta; não depende de cluster para documentar. | RFC/ADR apropriado e requisitos de infra entregues. |
| P3-03 | Instrumentar app/Lambda e preparar consumidor com testes. | Contratos JWT/eventos existentes. | PRs testados offline; sem PII; versão e idempotência cobertas. |
| P3-04 | Preparar consultas/painéis, documentação e roteiro. | Fontes de dados e contratos conhecidos. | Configuração versionada e revisão de métricas/documentos. |
| P3-05 | Integrar coleta/APM, canal e consumidor em staging. | Pessoa 2: #87, IAM, rede, mensageria e deploy. | Dados reais de teste aparecem em logs, métricas e traces; evento gera aviso. |
| P3-06 | Validar oito painéis, alertas e falhas controladas. | Coleta e dados sintéticos; Pessoa 1: #68. | Resultados reproduzíveis com consultas e evidências sanitizadas. |
| P3-07 | Reconciliar documentação e montar vídeo/PDF. | Versões implantadas e aceites técnicos. | Links, revisão da dupla e pacote final completo. |

P3-01 a P3-04 podem avançar durante a construção da infraestrutura. P3-05 a P3-07 precisam de ambiente e evidências; não bloquear documentação inicial esperando o cluster, nem declarar entrega operacional com mocks.

## 10. Documentação arquitetural e pacote final

Completar e revisar com Gustavo:

- Diagrama de componentes cloud com Gateway, Lambda de cliente, aplicação Kubernetes, banco, mensageria, consumidor e observabilidade; identificar componentes administrativos separadamente.
- Sequências de autenticação e abertura de OS, incluindo erros e fronteiras de autorização relevantes.
- RFCs de nuvem, banco gerenciado e autenticação; ADRs de comunicação/eventos, escalabilidade/HPA e decisões permanentes adicionais.
- Justificativa PostgreSQL, ER atualizado, relacionamentos, índices, consistência e ajustes de performance efetivamente adotados.
- READMEs dos quatro repositórios: propósito, tecnologias, pré-requisitos, execução, testes, variáveis sem segredos, build/deploy, diagramas, rollback, Swagger/Postman, URLs e responsável.

Reconciliar ADRs existentes antes de criar documentos sobre a mesma decisão. O runbook #68 ainda contém texto antigo sobre integração de #64–#67; registrar o estado real e resultados sem apagar alterações locais preexistentes. O plano #98 deve refletir Gustavo como responsável pelas Pessoas 1 e 2 e dar visibilidade ao consumidor/mensageria.

Para cada evidência, registrar requisito/issue, ambiente, commit/versão, data/hora, procedimento, resultado esperado/obtido e link sanitizado. Usar como ponto de partida [o runbook de homologação](../docs/validation/lambda-homologation.md), preenchido junto de Gustavo.

O vídeo deve ter **até 15 minutos**, com roteiro cronometrado para autenticação CPF, API protegida, CI/CD com deploy real, dashboards ao vivo, logs/traces e notificação de falha. Não apresentar build/push com deploy pulado como implantação concluída.

O PDF único deve consolidar links dos quatro repos, documentação, ambiente/evidências e vídeo público ou não listado, além da confirmação do acesso `soat-architecture`. O acesso foi confirmado apenas nos dois repos principais no retrato da auditoria; Gustavo verifica banco/cluster antes do fechamento.

## 11. Integração entre responsáveis e critérios de saída

| Receber de Gustavo | Entregar a Gustavo |
| --- | --- |
| Versões/commits, URLs e cenário funcional aprovado para #68. | Evidências de traces/logs/alertas relacionadas aos cenários. |
| Outputs de cluster/banco/eventos, rede e acesso gerenciado. | Requisitos mínimos de coleta/IAM/retenção, sem credenciais em documentos. |
| Contrato do produtor, topologia de entrega, retry e DLQ. | Consumidor testado, canal acordado e procedimento de reprocessamento. |
| Resultados de deploy, rollback, backup e calibração HPA. | Documentos reconciliados, painéis e roteiro final para revisão. |

O aceite da Pessoa 3 exige observabilidade integrada, alertas/notificações exercitados, oito painéis verificáveis e pacote documental revisado. CI verde e alta cobertura da aplicação não substituem esse aceite.

Riscos principais: PII em telemetria, volume/custo excessivo, alta cardinalidade, correlação divergente, avisos duplicados ou perdidos e documentação que descreve uma arquitetura não implantada. Mitigar com testes de sanitização/contrato, limites e amostragem aprovados, idempotência documentada e revisão contra evidências reais.

## 12. Checklist de conclusão

- [ ] PR #110 revisado/integrado e #93 concluída além da fatia inicial de logs.
- [ ] Ferramenta, retenção, coleta, custos e acesso operacional definidos.
- [ ] Logs JSON e correlação UUID funcionam em Gateway, Lambda, API e consumidor.
- [ ] Métricas e traces investigáveis, sem CPF/CNPJ, JWT ou segredos.
- [ ] Oito dashboards publicados e conferidos com dados sintéticos conhecidos.
- [ ] Thresholds e rotas de alerta acordados; disparo e recuperação testados.
- [ ] Consumidor valida evento/versão, deduplica e trata falha do provedor.
- [ ] Retry, DLQ, alarme e reprocessamento demonstrados em staging.
- [ ] #68/#87 possuem evidências operacionais fornecidas por esta frente.
- [ ] Diagramas, RFCs, ADRs, ER e READMEs dos quatro repos reconciliados.
- [ ] Acesso de avaliação confirmado em todos os repositórios por Gustavo.
- [ ] Vídeo de até 15 minutos e PDF com links revisados pela dupla.

As caixas permanecem abertas até existir evidência de execução ou revisão correspondente. Este plano não registra novas decisões como aceitas e não altera automaticamente issues, PRs ou infraestrutura.
