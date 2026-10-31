# Fase 3 - Divisao de responsabilidades entre tres pessoas

## 1. Proposito do documento

Este documento consolida a divisao de trabalho discutida para a terceira fase do Tech Challenge do Auto Shop System. O objetivo e transformar o enunciado da fase em tres frentes de trabalho com proprietarios claros, interfaces explicitas entre as pessoas e criterios objetivos de conclusao.

A divisao nao representa tres projetos isolados. As tres pessoas trabalham sobre uma unica entrega integrada, mas cada uma possui autoridade principal sobre um conjunto de componentes e entregaveis. Isso reduz conflitos de implementacao, evita que uma atividade obrigatoria fique sem responsavel e facilita a revisao por Pull Request.

Este planejamento considera:

- o enunciado da Fase 3;
- a arquitetura atual da aplicacao FastAPI;
- a separacao exigida em quatro repositorios;
- as definicoes realizadas para autenticacao por CPF e JWT;
- as issues da Pessoa 1 publicadas no GitHub;
- as dependencias entre aplicacao, infraestrutura, observabilidade e documentacao;
- a necessidade de demonstrar a solucao integrada em homologacao.

## 2. Objetivo da Fase 3

A Fase 3 deve elevar o sistema da oficina a um nivel de operacao corporativa, adicionando seguranca, escalabilidade, alta disponibilidade, automacao de deploy e visibilidade operacional.

Ao final da fase, a equipe deve demonstrar:

1. autenticacao de clientes por CPF utilizando uma Function Serverless;
2. emissao e validacao de JWT para consumo de APIs protegidas;
3. API Gateway controlando entrada, roteamento e protecao das APIs;
4. aplicacao principal executando em Kubernetes com capacidade de escala;
5. banco de dados gerenciado provisionado por Terraform;
6. infraestrutura Kubernetes provisionada por Terraform;
7. quatro repositorios independentes, todos com CI/CD e protecao de branch;
8. monitoramento de APIs, Kubernetes, healthchecks, uptime, falhas e integracoes;
9. logs estruturados e correlacionados;
10. dashboards operacionais e de negocio;
11. documentacao arquitetural completa;
12. demonstracao gravada e pacote final de entrega.

**Escopo de implantação AWS definido para esta entrega:** a equipe manterá o desenvolvimento diário local e demonstrará um único ambiente AWS de homologação, efêmero. Um ambiente AWS de produção, uma segunda conta e a promoção entre ambientes não são requisitos desta etapa; referências gerais a produção neste documento são metas futuras e não autorizam provisionamento.

## 3. Principio usado para dividir o trabalho

A divisao foi feita por fluxo de valor e por fronteira tecnica, e nao apenas por tecnologia.

| Pessoa | Frente principal | Resultado pelo qual responde |
| --- | --- | --- |
| Pessoa 1 | Identidade, autenticacao, autorizacao e integracao com a aplicacao | Um cliente ativo autentica por CPF, recebe JWT, acessa somente seus recursos e gera eventos tecnicos seguros quando o processamento da OS falha. |
| Pessoa 2 | Plataforma cloud, Terraform, Kubernetes, banco gerenciado, API Gateway e CI/CD | Os quatro repositorios possuem pipelines e a solucao pode ser provisionada e implantada de forma reproduzivel no unico ambiente AWS de homologacao desta entrega. |
| Pessoa 3 | Observabilidade, notificacoes, documentacao arquitetural e pacote de entrega | A operacao pode ser observada, falhas geram alertas/notificacoes, as decisoes estao documentadas e a entrega pode ser demonstrada e auditada. |

### 3.1 Regras de propriedade

- Cada atividade possui um unico responsavel final, ainda que dependa de colaboracao.
- Alteracoes em um repositorio de outra pessoa devem ocorrer por Pull Request e revisao do proprietario.
- Contratos compartilhados devem ser registrados antes da implementacao integrada.
- Segredos, credenciais, tokens e dados pessoais nunca devem ser adicionados ao Git.
- Homologacao deve ser validada antes de qualquer promocao para producao.
- A pessoa responsavel por um componente tambem responde pelos testes, README, pipeline e evidencias desse componente.

## 4. Estrutura planejada de repositorios

O enunciado exige quatro repositorios. A propriedade sugerida e:

| Repositorio | Conteudo principal | Proprietario primario | Colaboradores |
| --- | --- | --- | --- |
| `lambda-auth` | Function Serverless de autenticacao, emissao de JWT, JWKS, testes e empacotamento | Pessoa 1 | Pessoa 2 no deploy e IAM; Pessoa 3 em logs, metricas e alertas |
| `k8s-infra` | Cluster Kubernetes, rede de entrada, API Gateway/Ingress, HPA, configuracoes e Terraform | Pessoa 2 | Pessoa 1 nos contratos de rota; Pessoa 3 na coleta de telemetria |
| `database-infra` | Banco gerenciado, rede, seguranca, backups, parametros e Terraform | Pessoa 2 | Pessoa 1 no contrato de acesso; Pessoa 3 na documentacao do modelo e monitoramento |
| `auto-shop-system` ou `auto-shop-app` | Aplicacao FastAPI, frontend, dominio, migrations e validacao do JWT | Pessoa 1 para as mudancas funcionais da fase | Pessoa 2 no deploy Kubernetes; Pessoa 3 na instrumentacao e documentacao |

O dominio do cliente e as migrations continuam pertencendo a aplicacao principal. A Function consulta o cliente e seu status, mas nao se torna proprietaria do schema do cliente.

## 5. Pessoa 1 - Identidade, seguranca da aplicacao e integracao funcional

### 5.1 Missao

Entregar o fluxo funcional que liga cliente, autenticacao serverless, JWT, aplicacao principal e ordem de servico. A Pessoa 1 e responsavel por garantir que a autenticacao de cliente seja segura, separada da autenticacao administrativa e aplicada corretamente nas operacoes protegidas.

### 5.2 Responsabilidades detalhadas

#### 5.2.1 Status de acesso do cliente

- Introduzir no dominio o status explicito `Ativo` ou `Inativo`.
- Criar migration com valor padrao e backfill seguro para clientes existentes.
- Garantir que novos clientes sejam criados como ativos quando nenhum status for informado.
- Expor alteracao de status somente em rota administrativa autenticada.
- Manter os contratos publicos e administrativos retrocompativeis.
- Impedir valores de status fora do conjunto permitido.
- Cobrir dominio, persistencia, migration e rota HTTP com testes.

Entregavel associado: [issue #63](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/issues/63).

#### 5.2.2 Function Serverless de autenticacao por CPF

- Manter o repositorio `lambda-auth`.
- Disponibilizar o endpoint de autenticacao de cliente.
- Validar formato e digitos verificadores do CPF antes de consultar o banco.
- Consultar a existencia do cliente e seu status por meio de uma porta de consulta.
- Utilizar credencial de banco com privilegio minimo e, preferencialmente, somente leitura.
- Emitir token apenas para cliente ativo.
- Retornar a mesma resposta publica para cliente inexistente e cliente inativo, reduzindo enumeracao de cadastros.
- Tratar falhas de banco e assinatura sem expor detalhes internos.
- Garantir que CPF, nome, e-mail, telefone, token completo e segredos nao aparecam em logs.
- Manter testes unitarios, de contrato e de integracao com dependencias simuladas.

Contrato de sucesso esperado:

```json
{
  "access_token": "<jwt>",
  "token_type": "Bearer",
  "expires_in": 900
}
```

Entregavel associado: [issue #64](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/issues/64).

#### 5.2.3 Contrato JWT

A Pessoa 1 e responsavel por manter o contrato entre o emissor e a aplicacao principal.

Claims obrigatorias:

```json
{
  "sub": "<customer-id>",
  "principal_type": "customer",
  "scope": "customer",
  "iss": "<configured-issuer>",
  "aud": "auto-shop-api",
  "iat": 0,
  "exp": 0,
  "jti": "<unique-token-id>"
}
```

Regras:

- `sub` utiliza o identificador interno do cliente, nunca o CPF.
- O token nao inclui dados pessoais.
- O algoritmo aprovado para homologacao e `RS256`.
- A assinatura utiliza chave assimetrica gerenciada pelo AWS KMS.
- A chave publica e disponibilizada por JWKS.
- `kid`, `iss`, `aud` e TTL devem coincidir entre emissor e validador.
- O TTL maximo inicialmente acordado e 900 segundos.
- A inativacao impede novas emissoes; tokens ja emitidos permanecem validos ate expirarem.
- Rotacao de chave exige que o JWKS publique a chave antiga e a nova durante a janela de transicao.

#### 5.2.4 Validacao do JWT na aplicacao principal

- Aceitar JWT de cliente pelo cabecalho `Authorization: Bearer` somente nas rotas destinadas ao cliente.
- Validar assinatura, algoritmo, `iss`, `aud`, `exp`, `principal_type` e `scope`.
- Rejeitar `alg=none`, algoritmos diferentes do permitido e tokens sem expiracao.
- Criar uma abstracao de principal autenticado que diferencie explicitamente `customer` de `admin`.
- Preservar a autenticacao administrativa existente sem fallback entre os mecanismos.
- Disponibilizar `GET /api/v1/customer/me` como verificacao minima da identidade tecnica.
- Retornar apenas os dados necessarios e impedir cache de respostas sensiveis.
- Criar testes para token valido, expirado, adulterado, emissor incorreto, audiencia incorreta, escopo incorreto e ausencia de token.
- Manter testes de regressao das rotas administrativas.

Entregavel associado: [issue #65](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/issues/65).

#### 5.2.5 Autorizacao para consulta da propria ordem de servico

- Implementar `GET /api/v1/customer/service-orders/{service_order_id}`.
- Derivar o cliente exclusivamente do `sub` do JWT validado.
- Nao confiar em `customer_id` enviado em query string, corpo ou cabecalho.
- Consultar a OS no escopo do cliente sempre que o repositorio permitir.
- Retornar o mesmo resultado publico para OS inexistente e OS de outro cliente.
- Criar DTO especifico para a visao do cliente.
- Excluir CPF, dados de contato, dados de outros clientes e campos administrativos.
- Adicionar `Cache-Control: no-store` nas respostas do cliente.
- Cobrir tentativa de IDOR com dois clientes e duas ordens distintas.
- Preservar os fluxos publicos e administrativos existentes.

Entregavel associado: [issue #66](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/issues/66).

#### 5.2.6 Publicacao de evento de falha de OS

- Introduzir uma porta de saida para publicacao de eventos.
- Publicar `ServiceOrderProcessingFailed` em falhas operacionais inesperadas.
- Nao publicar evento para validacoes de dominio esperadas.
- Utilizar contrato versionado contendo `event_id`, `event_type`, `event_version`, `occurred_at`, `request_id`, `service_order_id` e `severity`.
- Propagar um correlation ID UUID valido.
- Realizar rollback antes da tentativa de publicacao quando houver transacao aberta.
- Utilizar estrategia best-effort na entrega inicial, sem outbox.
- Preservar a excecao original quando a publicacao falhar.
- Registrar apenas identificadores tecnicos, sem dados pessoais ou descricao sensivel da excecao.
- Criar testes com adaptador fake para publicacao unica, ausencia de evento em erro de dominio e falha do publicador.

Entregavel associado: [issue #67](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/issues/67).

#### 5.2.7 Validacao integrada em homologacao

A Pessoa 1 lidera a execucao funcional do fluxo integrado, mas depende da infraestrutura da Pessoa 2 e da telemetria preparada pela Pessoa 3.

Deve validar:

1. cliente ativo autentica e consulta a propria OS;
2. cliente inativo nao recebe token;
3. token expirado, adulterado ou com audiencia incorreta e rejeitado;
4. tentativa de consultar a OS de outro cliente e bloqueada;
5. autenticacao administrativa continua funcional;
6. falha operacional de OS produz o evento acordado;
7. resultados ficam registrados em evidencias sanitizadas e reproduziveis.

Entregavel associado: [issue #68](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/issues/68).

### 5.3 Limites de responsabilidade da Pessoa 1

A Pessoa 1 nao e a proprietaria primaria de:

- criacao de VPC, cluster Kubernetes, banco gerenciado ou API Gateway;
- criacao de chaves KMS, IAM, Secrets Manager ou EventBridge por Terraform;
- configuracao de HPA, ingress, DNS e certificados;
- dashboards de observabilidade;
- consumidor serverless de notificacao;
- gravacao e edicao do video final;
- documento final enviado ao portal.

Ela deve, entretanto, fornecer contratos, variaveis de ambiente, endpoints, healthchecks, metricas e requisitos de permissao para que as outras pessoas realizem essas atividades.

### 5.4 Definition of Done da Pessoa 1

- Issues funcionais implementadas e revisadas por Pull Request.
- Testes unitarios e de integracao cobrindo seguranca e regressao.
- Ausencia de CPF, token e segredo em logs ou evidencias.
- Contratos JWT, JWKS, eventos e endpoints documentados.
- Aplicacao e Lambda prontas para deploy automatizado.
- Fluxo completo validado em homologacao.
- Evidencias entregues para a Pessoa 3 incorporar na documentacao e no video.

## 6. Pessoa 2 - Plataforma cloud, infraestrutura e CI/CD

### 6.1 Missao

Construir a plataforma reproduzivel que executa a Function, a aplicacao principal e o banco de dados. A Pessoa 2 responde pelo provisionamento por Terraform, pela conectividade segura entre os componentes, pela escalabilidade do Kubernetes e pela automacao de entrega dos quatro repositorios.

### 6.2 Responsabilidades detalhadas

#### 6.2.1 Organizacao dos quatro repositorios

- Garantir a existencia e a delimitacao dos quatro repositorios obrigatorios.
- Configurar protecao da branch `main` ou `master`.
- Bloquear commits diretos na branch protegida.
- Exigir Pull Request para merge.
- Configurar checks obrigatorios antes do merge.
- Padronizar ambientes de homologacao e producao.
- Definir convencoes de tags, releases e versionamento de artefatos.
- Ajudar cada proprietario a integrar sua pipeline sem assumir a logica interna do componente.

#### 6.2.2 Infraestrutura Kubernetes

- Criar e manter o repositorio `k8s-infra`.
- Provisionar o cluster Kubernetes por Terraform.
- Configurar namespaces ou outra separacao equivalente entre ambientes.
- Configurar deployment, service, ingress e politicas de rede da aplicacao.
- Configurar readiness, liveness e startup probes.
- Configurar requests e limits de CPU e memoria.
- Implementar HPA com metricas e limites documentados.
- Preparar estrategia de rollout e rollback.
- Impedir que secrets reais sejam armazenados em manifests ou no estado versionado.
- Expor outputs necessarios para as pipelines e para a observabilidade.

#### 6.2.3 API Gateway e entrada da aplicacao

- Provisionar ou configurar o API Gateway escolhido.
- Encaminhar a rota de autenticacao para a Function Serverless.
- Encaminhar rotas da API principal para o servico Kubernetes.
- Configurar TLS, CORS e limites de payload.
- Configurar throttling e rate limiting antes de expor a autenticacao por CPF.
- Definir o comportamento `429` para excesso de tentativas.
- Propagar correlation ID entre Gateway, Lambda e aplicacao.
- Documentar URLs, stages, mappings e regras por ambiente.
- Coordenar com a Pessoa 1 os codigos de erro e os contratos de entrada e saida.

#### 6.2.4 Infraestrutura da Function Serverless

- Integrar o pacote produzido no repositorio `lambda-auth` ao ambiente cloud.
- Provisionar Function, log group, configuracoes e permissoes por Terraform.
- Provisionar ou referenciar a chave KMS aprovada.
- Disponibilizar variaveis `iss`, `aud`, `kid`, TTL e nomes de secrets por ambiente.
- Configurar acesso da Function ao banco usando privilegio minimo.
- Configurar timeouts, memoria, concorrencia e politicas de retry.
- Manter as permissoes IAM restritas aos recursos necessarios.
- Garantir que o deploy possa ser revertido.

A Pessoa 2 nao modifica a regra de autenticacao; recebe um artefato versionado e um contrato da Pessoa 1.

#### 6.2.5 Banco de dados gerenciado

- Criar e manter o repositorio `database-infra`.
- Provisionar o banco PostgreSQL gerenciado por Terraform.
- Configurar subnets, security groups e conectividade privada.
- Configurar backups, retencao, criptografia e restauracao.
- Definir parametros de capacidade e estrategia de escala.
- Criar separacao de credenciais entre aplicacao, Lambda e operacao.
- Garantir que a Lambda possua somente as permissoes de leitura necessarias.
- Disponibilizar secrets por mecanismo gerenciado, nunca por arquivos versionados.
- Coordenar a execucao de migrations da aplicacao sem transferir a propriedade do schema para a infraestrutura.
- Produzir outputs e instrucoes para conexao nos ambientes autorizados.

#### 6.2.6 Mensageria e permissoes de integracao

- Provisionar o EventBridge, fila ou topico escolhido para o evento de falha.
- Configurar permissao da aplicacao para publicar somente no destino autorizado.
- Configurar permissao do consumidor mantido pela Pessoa 3.
- Definir dead-letter queue quando aplicavel.
- Documentar retencao, retry e comportamento em indisponibilidade.
- Entregar nomes, ARNs ou identificadores por output seguro de infraestrutura.

#### 6.2.7 Pipelines de CI/CD

Cada um dos quatro repositorios deve possuir pipeline funcional. A Pessoa 2 define o padrao e garante a integracao de deploy.

Pipeline minima esperada:

1. instalacao reproduzivel de dependencias;
2. lint e verificacoes estaticas;
3. testes automatizados;
4. verificacao de seguranca e dependencias;
5. build do artefato ou imagem;
6. validacao de Terraform quando aplicavel;
7. publicacao versionada do artefato;
8. deploy automatico para homologacao na branch acordada;
9. promocao controlada para producao;
10. smoke test e mecanismo de rollback.

Para Terraform, incluir ao menos `fmt`, `validate`, analise do plano e aplicacao controlada. O estado remoto deve ser protegido e separado por ambiente.

### 6.3 Entregaveis da Pessoa 2

- Repositorios `k8s-infra` e `database-infra`.
- Estrutura de CI/CD nos quatro repositorios.
- API Gateway integrado com Lambda e aplicacao.
- Cluster Kubernetes escalavel com healthchecks.
- Banco gerenciado com rede, backup e secrets.
- IAM e conectividade com privilegio minimo.
- Recurso de mensageria necessario ao evento de falha.
- Ambientes de homologacao e producao documentados.
- Evidencia de deploy automatizado e rollback.
- Outputs necessarios para a Pessoa 3 configurar observabilidade.

### 6.4 Limites de responsabilidade da Pessoa 2

A Pessoa 2 nao e a proprietaria primaria de:

- validacao de CPF ou regra de status do cliente;
- definicao interna das claims do JWT;
- autorizacao de acesso a OS;
- classificacao das excecoes de dominio;
- conteudo de dashboards de negocio;
- elaboracao final de RFCs, ADRs e diagramas;
- roteiro e edicao do video final.

Ela participa dessas decisoes quando elas afetam infraestrutura, custo, seguranca, disponibilidade ou operacao.

### 6.5 Definition of Done da Pessoa 2

- Terraform validado e revisado.
- Nenhum segredo presente no repositorio ou no estado exposto.
- Branches protegidas e Pull Requests obrigatorios.
- Deploy de homologacao executado automaticamente.
- API Gateway roteando Lambda e aplicacao.
- Aplicacao saudavel no Kubernetes e HPA verificavel.
- Banco acessivel somente pelos componentes autorizados.
- Mensageria e IAM disponiveis para o fluxo de falha.
- Procedimentos de rollback e recuperacao documentados.
- Informacoes de ambiente entregues para Pessoas 1 e 3.

## 7. Pessoa 3 - Observabilidade, notificacoes e documentacao da entrega

### 7.1 Missao

Garantir que a solucao seja observavel, que falhas relevantes resultem em alerta ou notificacao e que toda a arquitetura possa ser compreendida, reproduzida e demonstrada. A Pessoa 3 transforma a implementacao das outras frentes em evidencias operacionais e documentais.

### 7.2 Responsabilidades detalhadas

#### 7.2.1 Padrao de observabilidade

- Selecionar e documentar Datadog, New Relic ou ferramenta equivalente.
- Definir padrao de logs estruturados em JSON.
- Definir campos minimos de log, incluindo timestamp, nivel, servico, ambiente, versao e correlation ID.
- Impedir que CPF, CNPJ, tokens, dados pessoais e segredos aparecam nos logs.
- Definir propagacao de correlation ID entre Gateway, Lambda, aplicacao, banco e consumidor.
- Configurar retencao, busca e filtros dos logs.
- Definir metricas e traces necessarios para a demonstracao.
- Abrir Pull Requests de instrumentacao nos repositorios dos proprietarios quando necessario.

#### 7.2.2 Monitoramento tecnico

Configurar monitoramento para:

- latencia das APIs;
- taxa de requisicoes e codigos HTTP;
- erros da Lambda;
- duracao, cold start, timeout e throttling da Lambda;
- CPU e memoria dos workloads Kubernetes;
- reinicios e indisponibilidade de pods;
- estado de readiness e liveness;
- uptime dos endpoints principais;
- conexoes e saude do banco gerenciado;
- falhas nas integracoes;
- falhas de publicacao e consumo de eventos;
- pipeline e deploy quando a ferramenta permitir.

#### 7.2.3 Dashboards obrigatorios

Criar dashboards que apresentem:

1. volume diario de ordens de servico;
2. tempo medio de execucao por status, incluindo Diagnostico, Execucao e Finalizacao;
3. erros e falhas nas integracoes;
4. latencia e disponibilidade das APIs;
5. CPU e memoria do Kubernetes;
6. healthchecks e uptime;
7. falhas no processamento de ordens de servico;
8. visao de correlation ID para investigar uma requisicao ponta a ponta.

Cada painel deve registrar fonte dos dados, periodo, unidade, filtros e criterio de alerta.

#### 7.2.4 Alertas e notificacoes serverless

- Implementar o consumidor serverless do evento `ServiceOrderProcessingFailed`.
- Validar a versao do evento antes do processamento.
- Deduplicar pelo `event_id` quando o provedor exigir semantica idempotente.
- Gerar notificacao para o canal acordado sem incluir dados pessoais.
- Correlacionar a notificacao por `event_id`, `request_id` e `service_order_id`.
- Configurar retry e tratamento de mensagens nao processadas.
- Criar alarme para falhas repetidas do consumidor.
- Testar evento valido, evento duplicado, versao desconhecida e falha do provedor de notificacao.
- Documentar como reproduzir o alerta de forma controlada em homologacao.

#### 7.2.5 Documentacao arquitetural

A Pessoa 3 coordena a producao e a consistencia do conjunto documental. As Pessoas 1 e 2 fornecem o conteudo tecnico de suas areas e revisam os documentos.

Documentos obrigatorios:

- diagrama de componentes com nuvem, API Gateway, Lambda, Kubernetes, banco, mensageria e monitoramento;
- diagrama de sequencia do fluxo de autenticacao;
- diagrama de sequencia do fluxo de abertura de ordem de servico;
- RFC para escolha da nuvem;
- RFC para escolha do banco gerenciado;
- RFC para estrategia de autenticacao;
- ADR para padrao de comunicacao e eventos;
- ADR para estrategia de escalabilidade e HPA;
- ADRs adicionais para decisoes permanentes relevantes;
- justificativa formal para PostgreSQL;
- diagrama entidade-relacionamento atualizado;
- explicacao de relacionamentos, indices, consistencia e ajustes de performance.

As decisoes de autenticacao e evento ja registradas devem ser reconciliadas com a implementacao final, sem duplicar ou contradizer os ADRs existentes.

#### 7.2.6 READMEs e documentacao de uso

Garantir que cada repositorio apresente:

- proposito e limite de responsabilidade;
- tecnologias utilizadas;
- pre-requisitos;
- passos de execucao local;
- comandos de teste;
- variaveis de ambiente sem valores secretos;
- processo de build e deploy;
- diagrama especifico do repositorio;
- estrategia de rollback;
- link para Swagger ou colecao Postman;
- links para ambiente ativo quando aplicavel;
- responsavel e canal de suporte da equipe.

#### 7.2.7 Evidencias, video e pacote final

- Criar roteiro de demonstracao com duracao maxima de 15 minutos.
- Coordenar a gravacao de autenticacao por CPF.
- Demonstrar consumo de API protegida.
- Demonstrar pipeline de CI/CD e deploy automatizado.
- Demonstrar dashboard com analise ao vivo.
- Demonstrar logs e traces correlacionados.
- Evitar mostrar segredos, tokens completos, CPFs reais ou paineis administrativos sensiveis.
- Consolidar links dos quatro repositorios.
- Consolidar links das documentacoes.
- Consolidar link do video publico ou nao listado.
- Confirmar o usuario `soat-architecture` em todos os repositorios.
- Produzir o PDF unico exigido para envio no Portal do Aluno.
- Manter uma checklist final com responsavel e evidencia para cada requisito.

### 7.3 Entregaveis da Pessoa 3

- Instrumentacao e padroes de logs estruturados.
- Integracao com a plataforma de observabilidade.
- Dashboards tecnicos e de negocio.
- Alertas de disponibilidade, recursos, integracao e falha de OS.
- Consumidor serverless de notificacao.
- Diagramas, RFCs, ADRs e justificativa do banco.
- READMEs completos e consistentes.
- Colecao de evidencias sanitizadas.
- Roteiro e video de demonstracao.
- PDF final de entrega.

### 7.4 Limites de responsabilidade da Pessoa 3

A Pessoa 3 nao e a proprietaria primaria de:

- provisionamento base de VPC, Kubernetes, banco ou API Gateway;
- regra de negocio de autenticacao e autorizacao;
- migration de status do cliente;
- criacao do evento dentro do dominio da aplicacao;
- configuracao de acesso da Lambda ao banco.

Ela pode alterar instrumentacao nos componentes, mas deve fazer isso em alinhamento com o proprietario e sem mover regra de negocio para a camada de observabilidade.

### 7.5 Definition of Done da Pessoa 3

- Logs JSON pesquisaveis e correlacionados entre os componentes.
- Dashboards exibindo todos os indicadores obrigatorios.
- Alertas testados em homologacao.
- Consumidor de notificacao processando o contrato versionado.
- Documentacao arquitetural revisada pelas Pessoas 1 e 2.
- READMEs completos nos quatro repositorios.
- Evidencias sem dados sensiveis.
- Video dentro do limite de 15 minutos.
- PDF final contendo todos os links e confirmacoes exigidos.

## 8. Matriz de responsabilidades

Legenda:

- **R**: executa a atividade;
- **A**: responde pelo resultado final;
- **C**: deve ser consultado;
- **I**: deve ser informado.

| Entregavel | Pessoa 1 | Pessoa 2 | Pessoa 3 |
| --- | --- | --- | --- |
| Status ativo/inativo do cliente | A/R | I | I |
| Function de autenticacao por CPF | A/R | C | C |
| Contrato JWT e JWKS | A/R | C | C |
| Validacao JWT na aplicacao | A/R | I | C |
| Rota de consulta da propria OS | A/R | I | C |
| Evento de falha da OS | A/R | C | C |
| Repositorio `lambda-auth` | A/R | C | C |
| Repositorio `k8s-infra` | C | A/R | C |
| Repositorio `database-infra` | C | A/R | C |
| Aplicacao principal no Kubernetes | C | A/R | C |
| API Gateway e rate limiting | C | A/R | C |
| Cluster, HPA, rede e ingress | I | A/R | C |
| Banco gerenciado e conectividade | C | A/R | C |
| IAM, KMS, secrets e mensageria | C | A/R | C |
| Pipelines de CI/CD | C | A/R | C |
| Logs estruturados e correlacao | C | C | A/R |
| Metricas, traces e dashboards | C | C | A/R |
| Alertas e consumidor de notificacao | C | C | A/R |
| Diagramas, RFCs e ADRs | C | C | A/R |
| Justificativa e diagrama do banco | C | C | A/R |
| READMEs dos repositorios | R | R | A/C |
| Validacao integrada em homologacao | A/R | R | R |
| Video e PDF final | C | C | A/R |

## 9. Dependencias e pontos de handoff

### 9.1 Pessoa 1 para Pessoa 2

A Pessoa 1 entrega:

- imagem ou pacote versionado da aplicacao e da Lambda;
- healthchecks;
- rotas do Gateway;
- variaveis de ambiente esperadas;
- contrato JWT e JWKS;
- requisitos de acesso ao banco;
- contrato do evento;
- limites de timeout e comportamento de erro;
- procedimentos de smoke test.

A Pessoa 2 devolve:

- URLs e stages de homologacao;
- nomes seguros ou referencias dos secrets;
- identificadores de KMS e mensageria;
- configuracao de `iss`, `aud` e `kid` por ambiente;
- conectividade e credenciais com privilegio minimo;
- evidencia do deploy;
- procedimento de rollback.

### 9.2 Pessoa 2 para Pessoa 3

A Pessoa 2 entrega:

- endpoints de metricas e healthchecks;
- integracao de logs dos componentes;
- identificadores de cluster, workloads, banco, Lambda e Gateway;
- outputs necessarios para configurar monitores;
- limites de CPU, memoria e escala;
- configuracao de eventos e dead-letter queue;
- ambientes e janelas de teste.

A Pessoa 3 devolve:

- dashboards;
- monitores e limites de alerta;
- consultas de log;
- validacao da propagacao de correlation ID;
- relatorio de lacunas de telemetria;
- evidencias para a demonstracao.

### 9.3 Pessoa 3 para Pessoa 1

A Pessoa 3 entrega:

- formato de log estruturado;
- biblioteca ou convencao de instrumentacao;
- campos obrigatorios para traces e metricas;
- feedback sobre dados sensiveis observados;
- resultado dos testes de alerta e evento;
- roteiro dos cenarios que precisam aparecer no video.

A Pessoa 1 devolve:

- pontos de instrumentacao na aplicacao e Lambda;
- eventos de dominio ou integracao acordados;
- massa de dados sintetica;
- procedimento controlado para provocar falha de OS;
- evidencias da autenticacao e autorizacao.

## 10. Ordem recomendada de execucao

### Marco 0 - Alinhamento de contratos

Participantes: todos.

- confirmar nuvem, regiao e ambientes;
- congelar nomes dos quatro repositorios;
- aprovar contrato JWT;
- aprovar rotas do API Gateway;
- aprovar contrato do evento de falha;
- aprovar estrategia de logs e correlation ID;
- definir criterios de homologacao e producao;
- registrar decisoes em RFCs ou ADRs.

### Marco 1 - Fundacao dos repositorios e pipelines

Responsavel principal: Pessoa 2.

- criar repositorios faltantes;
- proteger branches;
- instalar pipelines iniciais;
- validar Dockerfiles e Terraform;
- preparar ambientes sem executar producao prematuramente.

Em paralelo, a Pessoa 1 prepara aplicacao e Lambda, enquanto a Pessoa 3 define telemetria e estrutura documental.

### Marco 2 - Entregas independentes

- Pessoa 1 conclui status do cliente, Lambda, JWT, rota do cliente e evento.
- Pessoa 2 conclui Gateway, cluster, banco, IAM, mensageria e deploy.
- Pessoa 3 conclui consumidor, instrumentacao inicial, dashboards e esqueleto documental.

### Marco 3 - Integracao em homologacao

Participantes: todos.

Sequencia critica:

```text
Banco gerenciado e migrations
          |
          v
Lambda de autenticacao ---> API Gateway
          |                     |
          v                     v
     Emissao do JWT ---> Aplicacao no Kubernetes
                              |
                              v
                     Consulta protegida da OS
                              |
                              v
                     Evento de falha da OS
                              |
                              v
                  Consumidor, alerta e dashboard
```

### Marco 4 - Evidencias e entrega

Responsavel principal: Pessoa 3.

- executar a checklist de homologacao;
- registrar commits e versoes implantadas;
- capturar evidencias sanitizadas;
- revisar diagramas e decisoes;
- gravar o video;
- validar links e permissoes dos repositorios;
- montar o PDF final;
- realizar revisao cruzada antes do envio.

## 11. Caminho critico

O caminho critico da entrega e:

1. definicao do contrato JWT e do acesso ao cliente;
2. disponibilidade do banco gerenciado e da conectividade;
3. deploy da Lambda e publicacao do JWKS;
4. configuracao do API Gateway com rate limiting;
5. deploy da aplicacao no Kubernetes;
6. validacao do JWT pela aplicacao;
7. autorizacao da consulta da OS;
8. publicacao e consumo do evento de falha;
9. observabilidade do fluxo ponta a ponta;
10. evidencias, video e pacote final.

Qualquer atraso nos itens 2, 3, 4 ou 5 bloqueia a issue de homologacao e impede a demonstracao completa.

## 12. Riscos e mitigacoes

| Risco | Impacto | Responsavel por liderar a mitigacao | Mitigacao |
| --- | --- | --- | --- |
| CPF tratado como prova forte de identidade | Alto | Pessoa 1 | Limitar ao escopo academico, usar TTL curto e registrar OTP como evolucao antes de producao real. |
| Enumeracao de clientes | Alto | Pessoa 1 | Resposta uniforme para inexistente/inativo e rate limiting no Gateway. |
| Vazamento de CPF, JWT ou segredo | Alto | Todos | Logs sanitizados, secret manager, revisao de evidencias e testes de ausencia de PII. |
| Divergencia entre emissor e validador JWT | Alto | Pessoas 1 e 2 | Configuracao unica por ambiente e teste integrado de `iss`, `aud`, `kid` e JWKS. |
| Infraestrutura gerar custo inesperado | Alto | Pessoa 2 | Planejar custo, aplicar primeiro em homologacao e exigir aprovacao antes de recursos cobraveis. |
| Terraform destruir recurso ou banco | Alto | Pessoa 2 | Plano revisado, protecao contra destruicao, backups e aplicacao controlada. |
| Evento best-effort ser perdido | Medio | Pessoas 1, 2 e 3 | Alertar falha de publicacao, DLQ no consumidor e registrar a limitacao do modelo sem outbox. |
| Dashboards sem dados suficientes | Medio | Pessoa 3 | Definir telemetria antes da integracao e executar testes de carga/fluxo controlados. |
| Repositorios ficarem inconsistentes | Medio | Pessoa 2 | Templates de CI, regras de branch e checklist comum. |
| Documentacao divergir da implementacao | Medio | Pessoa 3 | Revisao dos proprietarios e atualizacao dos ADRs no fechamento de cada marco. |
| Video exceder 15 minutos ou expor dados | Medio | Pessoa 3 | Roteiro cronometrado, dados sinteticos e revisao da gravacao antes do upload. |

## 13. Situacao registrada em 22 de outubro de 2026

Na data desta consolidacao:

- os repositorios `auto-shop-system` e `lambda-auth` estao visiveis na organizacao conectada;
- as issues [#63](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/issues/63), [#64](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/issues/64), [#65](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/issues/65), [#66](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/issues/66) e [#67](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/issues/67) estao encerradas como concluidas;
- a issue [#68](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/issues/68) esta aberta e depende da infraestrutura integrada de homologacao;
- a implementacao de autenticacao utiliza como referencia RS256, KMS, JWKS e TTL maximo de 900 segundos;
- a consulta da OS utiliza autorizacao por propriedade e resposta uniforme para recurso inexistente ou alheio;
- o evento de falha foi definido como best-effort, sem outbox nesta entrega;
- o rate limiting da rota de autenticacao permanece responsabilidade da infraestrutura;
- a validacao integrada deve usar dados sinteticos e evidencias sanitizadas.

O estado acima e um retrato da data informada. O fechamento da issue #68 deve atualizar este documento ou apontar para o relatorio final de homologacao.

## 14. Checklist final por pessoa

### Pessoa 1

- [ ] Status do cliente aplicado e testado.
- [ ] Lambda valida CPF, consulta status e emite JWT.
- [ ] JWKS publicado e contrato alinhado com a aplicacao.
- [ ] JWT de cliente validado sem afetar administradores.
- [ ] Cliente acessa somente a propria OS.
- [ ] Evento de falha publicado sem PII.
- [ ] Testes de seguranca e regressao executados.
- [ ] Fluxo funcional validado em homologacao.
- [ ] Evidencias sanitizadas entregues.

### Pessoa 2

- [ ] Quatro repositorios disponiveis e protegidos.
- [ ] CI/CD funcional em todos os repositorios.
- [ ] API Gateway roteando e limitando tentativas.
- [ ] Lambda implantada com IAM e KMS adequados.
- [ ] Cluster Kubernetes operacional e escalavel.
- [ ] Banco gerenciado operacional e protegido.
- [ ] Secrets fora do codigo e do Git.
- [ ] Event bus e permissoes configurados.
- [ ] Homologacao implantada e reproduzivel.
- [ ] Rollback e recuperacao documentados.

### Pessoa 3

- [ ] Logs JSON e correlation ID funcionando.
- [ ] Metricas e traces disponiveis.
- [ ] Dashboards obrigatorios publicados.
- [ ] Alertas testados.
- [ ] Consumidor de notificacao operacional.
- [ ] Diagramas de componentes e sequencia finalizados.
- [ ] RFCs, ADRs e documentacao do banco revisados.
- [ ] READMEs completos nos quatro repositorios.
- [ ] Video de ate 15 minutos publicado.
- [ ] PDF final com links e confirmacoes preparado.

## 15. Criterio de sucesso da equipe

A Fase 3 somente pode ser considerada concluida quando os tres resultados estiverem presentes ao mesmo tempo:

1. **Fluxo funcional seguro:** autenticacao por CPF, JWT, autorizacao de cliente e evento de falha funcionando.
2. **Plataforma reproduzivel:** infraestrutura provisionada por Terraform, Kubernetes e banco gerenciado operacionais, API Gateway configurado e deploy automatizado.
3. **Operacao demonstravel:** logs, traces, dashboards, alertas, notificacoes, documentacao e video comprovando o funcionamento ponta a ponta.

Concluir apenas uma ou duas frentes nao atende ao objetivo do Tech Challenge. A responsabilidade final e coletiva, enquanto a responsabilidade de execucao permanece distribuida conforme este documento.
