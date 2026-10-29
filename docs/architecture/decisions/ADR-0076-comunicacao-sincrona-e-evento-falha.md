# ADR-0076: Comunicação síncrona e evento de falha operacional

- **Status:** aceito para o desenho; entrega e validação do destino pendentes
- **Data:** 2026-10-27
- **Issues:** [auto-shop-system #67](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/issues/67), [auto-shop-system #117](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/issues/117), [auto-shop-system #68](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/issues/68)

## Contexto

As operações de API precisam devolver o resultado de uma ação, como abrir uma OS ou consultar seu estado. Falhas operacionais inesperadas também precisam gerar aviso sem fazer o usuário esperar pelo canal de notificação.

## Decisão

- Usar REST síncrono para operações cujo resultado é necessário na resposta, incluindo abertura e consulta de OS.
- Em falha inesperada durante o processamento da OS, desfazer a transação e tentar publicar ServiceOrderProcessingFailed v1 no EventBridge.
- A publicação é best-effort e não substitui a exceção original nem altera a resposta de falha da aplicação.
- O consumidor de notificação encaminha o evento válido para SNS/e-mail. Falha de entrega deve usar retry e DLQ SQS conforme a issue #117.
- O contrato carrega identificadores técnicos de correlação e da OS, sem CPF, nome, token ou outros dados pessoais.
- O produtor e a aplicação não criam recursos de EventBridge, SNS ou SQS; a configuração pertence à infraestrutura.

## Alternativas consideradas

- **E-mail síncrono na requisição:** aumenta a latência e acopla o resultado de negócio à disponibilidade do provedor de e-mail.
- **Publicar todas as ações como eventos:** amplia a complexidade e não atende às respostas imediatas esperadas pela API.
- **Outbox transacional:** oferece garantias adicionais de publicação, mas está fora do escopo implementado. A decisão registra o comportamento best-effort.

## Consequências e validação

- A resposta síncrona confirma o resultado persistido, não a entrega de e-mail.
- A perda da tentativa de publicação continua possível e precisa aparecer em logs correlacionáveis.
- Event bus, regra, alvo SNS, retry e DLQ permanecem pendentes na issue #117.
- A execução do cenário completo e a evidência sanitizada permanecem na issue #68.

## Referências

- [ADR-0066/0067: consulta de OS e evento operacional](ADR-0066-0067-os-cliente-e-evento-de-falha.md)
- [Amazon EventBridge targets and retry policy](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-targets.html)
- [Amazon SNS](https://docs.aws.amazon.com/sns/latest/dg/welcome.html)
