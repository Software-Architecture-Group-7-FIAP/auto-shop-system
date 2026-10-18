# ADR-0066/0067: Consulta da OS pelo cliente e evento operacional

- **Status:** Proposta para revisão do grupo
- **Data:** 2026-10-18
- **Issues:** [#66](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/issues/66) e [#67](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/issues/67)

## Visão da OS para o cliente

A rota `GET /api/v1/customer/service-orders/{service_order_id}` exige um JWT de cliente e consulta a OS já limitada pelo identificador do cliente autenticado. A resposta contém somente identificador e status da OS, datas, total e linhas com serviço/produto, quantidade e preço unitário. Não inclui CPF, nome, contato, placa, veículo, orçamento, mecânico ou identificador do cliente.

Uma OS inexistente e uma OS pertencente a outra pessoa retornam o mesmo `404` com a mesma mensagem. Tentativas sem resultado geram log correlacionável com identificador da OS e correlation ID UUID, sem dados pessoais ou token. Respostas de cliente usam `Cache-Control: no-store`.

## Evento de falha no processamento

Os casos de uso administrativos de enfileirar, iniciar e finalizar uma OS publicam `ServiceOrderProcessingFailed` somente quando ocorre uma exceção inesperada. Erros de domínio conhecidos seguem o fluxo existente sem gerar evento. O contrato versão 1 contém `event_id`, `event_type`, `event_version`, `occurred_at`, `request_id`, `service_order_id` e `severity`.

Em uma falha inesperada, a aplicação tenta primeiro desfazer a transação e depois publica no EventBridge configurado em `SERVICE_ORDER_EVENT_BUS_NAME`. A publicação é best-effort e não usa outbox nesta entrega. Se rollback ou publicação falhar, a aplicação registra somente identificadores técnicos; preserva a exceção original e a resposta HTTP existente. A indisponibilidade do publicador não pode esconder a falha de publicação.

O `X-Correlation-ID` UUID tem precedência sobre o `X-Request-ID`. Valores ausentes ou fora do formato UUID são substituídos por um novo UUID antes de entrarem no log ou no evento. Os adaptadores AWS usam timeout curto e uma tentativa limitada; a aplicação não cria o event bus nem permissões IAM.

## Alinhamentos pendentes

- O grupo deve revisar a lista de campos da visão do cliente e confirmar o contrato HTTP uniforme de `404`.
- A pessoa responsável pelo consumidor serverless deve confirmar EventBridge e a semântica best-effort sem outbox.
- Event bus, permissões IAM e ambiente de homologação dependem das issues de infraestrutura. Nenhum recurso AWS foi criado ou consultado nesta implementação.
