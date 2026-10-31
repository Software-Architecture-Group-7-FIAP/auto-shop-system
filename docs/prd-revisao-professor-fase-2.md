# PRD — Correções da avaliação do Trabalho Regular, Fase 2

Issue principal: [#101](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/issues/101)

## Problem Statement

A avaliação da Fase 2 reconheceu que os principais fluxos de abertura e consulta de OS, orçamento, CI/CD, Docker, Kubernetes e Terraform estão implementados. A nota 81/90 aponta quatro frentes de melhoria: cobertura de testes nos fluxos críticos, especialmente nas transições de aprovação e recusa de orçamento; alinhamento da listagem de OS com prioridade, antiguidade e exclusão lógica; redução de duplicação e uniformização do tratamento de erros; e definição/validação das métricas do HPA.

O repositório já contém parte das correções de listagem: a API filtra OS encerradas por padrão, permite incluí-las explicitamente e possui ordenação por status e antiguidade coberta por testes. Porém, a fila de execução ordena pelo campo `Priority` (`Urgente`, `Alta`, `Normal`, `Baixa`) e a listagem administrativa não usa essa prioridade; a tela Angular também envia `created_at_asc`. Além disso, a regra de prioridade da OS permite alteração após o encerramento. O trabalho deve alinhar a listagem com a prioridade operacional e preservar o comportamento de exclusão lógica já existente.

## Solution

Completar a cobertura dos caminhos de decisão de orçamento e confirmar seus efeitos sobre OS/reservas; ordenar a lista operacional pela prioridade da OS e antiguidade; centralizar o mapeamento de erros de domínio para respostas HTTP consistentes; e validar o HPA com métricas disponíveis, ownership coerente de réplicas e calibração baseada em medições de carga.

## User Stories

1. Como responsável pela oficina, quero comprovar por testes os caminhos de aprovação e recusa do orçamento, para detectar regressões nas transições e nos efeitos sobre a OS.
2. Como atendente, quero ver as OS urgentes antes das menos prioritárias e as mais antigas primeiro dentro de cada nível, para priorizar o trabalho corretamente.
3. Como atendente, quero que OS encerradas saiam da lista operacional sem serem apagadas, e que continuem acessíveis quando eu solicitar sua inclusão.
4. Como mantenedor da API, quero um único contrato de erros de domínio, para que clientes e rotas recebam respostas consistentes e o código evite conversões duplicadas.
5. Como operador da aplicação, quero que o HPA use metas apoiadas por medições e métricas disponíveis, para escalar sem competir com os manifests ou o Terraform pelo número de réplicas.

## Implementation Decisions

- A baseline da auditoria é `origin/main` em `7cfcc94`, após atualização do usuário.
- A lista administrativa padrão já exclui `Finalizada` e `Entregue`; `include_closed=true` e filtros explícitos por status permitem consultá-las sem exclusão física. Preservar esse comportamento.
- A listagem operacional ordena pelo campo `Priority` da OS (`Urgente`, `Alta`, `Normal`, `Baixa`) e usa antiguidade e `id` crescente como desempates. A ordenação antiga por status permanece explícita para compatibilidade; a tela usa `priority` como padrão.
- Impedir alteração de prioridade de OS em estados encerrados, conforme os requisitos funcionais existentes.
- A cobertura de orçamento deve verificar aprovação e recusa pela borda HTTP, transições válidas/inválidas, repetição/decisão oposta e efeitos colaterais observáveis. Manter as regras de negócio atuais salvo se um teste evidenciar defeito.
- Padronizar erros de domínio com um tratamento central da aplicação, mantendo códigos HTTP e os campos de resposta compatíveis com consumidores atuais.
- Ajustar métricas, `requests`/`limits`, mínimo/máximo e comportamento de escala do HPA somente com base em um perfil de carga documentado; manter o mesmo contrato em manifests e Terraform.
- Remover configurações declarativas conflitantes de réplicas onde o HPA deve ser a fonte de escala; manter overlays locais compatíveis com os limites configurados.
- Não alterar orçamento, autorização, ciclo de vida de OS, API pública ou infraestrutura além dos critérios de aceite destas atividades.

## Testing Decisions

- Testes unitários devem cobrir transições de domínio e políticas puras.
- Testes de integração HTTP devem confirmar os contratos de aprovação/recusa, as respostas de erro e os efeitos persistidos nas OS/reservas.
- Testes da listagem devem cobrir filtro padrão de encerradas, inclusão explícita, prioridade da OS (`Urgente`, `Alta`, `Normal`, `Baixa`), antiguidade, desempate determinístico e parâmetros Angular; `status_priority` fica coberto como ordenação explícita legada.
- Validação do HPA deve usar um cluster de teste com Metrics Server ativo e carga controlada, verificando que o autoscaler recebe métricas e altera a escala conforme as metas definidas.
- Seguir os padrões existentes: `tests/unit/budget_approval`, `tests/integration/test_service_order_listing_api.py` e o pipeline em `.github/workflows/security.yml`.
- Preservar o gate de cobertura já configurado, sem usar a porcentagem global como substituto de cobertura dos cenários críticos.

## Out of Scope

- Novas funcionalidades de autenticação de cliente por CPF ou JWT de cliente.
- Criação ou separação de repositórios.
- Alterações de regras de negócio não apontadas na avaliação da Fase 2.
- Redesenho da infraestrutura Kubernetes/Terraform, banco ou pipeline além do necessário para validar e corrigir o HPA.
- Deploy em produção ou alteração de valores reais de ambiente.

## Further Notes

- Itens da avaliação que já estão atendidos devem permanecer cobertos pelos testes existentes, não gerar trabalho duplicado.
- O feedback não atribui cada ajuste a uma pessoa específica; este PRD organiza as tarefas por lacuna técnica e não inventa responsáveis.
- Sequência sugerida: testes de orçamento e correções de listagem podem avançar em paralelo; centralização de erros deve preservar contratos; a calibração do HPA depende da execução e registro do perfil de carga.

## Decomposição em issues

1. [F2-01 — Testar transições de orçamento](issues/revisao-fase-2/F2-01-testar-transicoes-de-orcamento.md) · [GitHub #102](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/issues/102)
2. [F2-02 — Listagem, prioridade, antiguidade e encerradas](issues/revisao-fase-2/F2-02-listagem-prioridade-antiguidade-e-encerradas.md) · [GitHub #103](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/issues/103)
3. [F2-03 — Uniformizar tratamento de erros](issues/revisao-fase-2/F2-03-uniformizar-tratamento-de-erros.md) · [GitHub #104](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/issues/104)
4. [F2-04 — Calibrar HPA](issues/revisao-fase-2/F2-04-calibrar-hpa.md) · complementar a issue existente [#78 — Configuração do HPA](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/issues/78)
