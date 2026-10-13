## Parent

- PRD #101 — [Correções da avaliação do professor, Fase 2](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/issues/101)

---

### 📖 User Story

**Como** atendente da oficina
**Quero** uma listagem de OS que respeite prioridade operacional, antiguidade e visibilidade das ordens encerradas
**Para que** eu trabalhe na ordem correta sem apagar o histórico

---

### 🏛️ Contexto

- **Bounded Context:** Gestão de Ordem de Serviço
- **Agregado/Entidade Afetada:** Ordem de Serviço
- **PRD pai:** [Correções da avaliação da Fase 2](../../prd-revisao-professor-fase-2.md)

---

### ✅ Critérios de Aceite

- [ ] **Cenário 1: A tela adota a ordenação padrão da API**
  - **Dado que** o atendente abre a listagem sem escolher outra ordenação
  - **Quando** a tela consulta a API
  - **Então** deve enviar `priority` como ordenação padrão

- [ ] **Cenário 2: Maior urgência aparece primeiro**
  - **Dado que** existem OS com prioridades `Urgente`, `Alta`, `Normal` e `Baixa`
  - **Quando** a listagem padrão for exibida
  - **Então** a ordem deve ser `Urgente`, `Alta`, `Normal` e `Baixa`, independentemente do status

- [ ] **Cenário 3: Antiguidade desempata prioridades iguais**
  - **Dado que** existem OS com a mesma prioridade
  - **Quando** a listagem padrão for exibida
  - **Então** as OS mais antigas devem aparecer primeiro, com `id` crescente como desempate final

- [ ] **Cenário 4: Ordens encerradas são ocultas sem serem excluídas**
  - **Dado que** existem OS `Finalizada` ou `Entregue`
  - **Quando** a listagem padrão for consultada
  - **Então** elas não devem aparecer na lista operacional
  - **E** devem continuar persistidas e acessíveis com o filtro de encerradas ou um filtro explícito de status

- [ ] **Cenário 5: Prioridade não pode ser alterada em OS encerrada**
  - **Dado que** uma OS está `Finalizada` ou `Entregue`
  - **Quando** alguém tentar alterar sua prioridade
  - **Então** o domínio/API deve rejeitar a operação sem modificar a OS

- [ ] **Cenário 6: Paginação e filtro mantêm a ordenação**
  - **Dado que** a consulta contém status e paginação
  - **Quando** a API retornar uma página
  - **Então** a ordenação deve permanecer estável entre páginas e respeitar os filtros solicitados

---

### 🛡️ Definition of Ready (DoR) - Checklist

- [ ] A User Story está clara e focada no trabalho operacional.
- [ ] A regra atual de estados operacionais/encerrados foi confirmada.
- [ ] Os critérios diferenciam ocultar uma OS da sua exclusão física.
- [ ] Os testes cobrem o parâmetro enviado pela tela, API e regra de prioridade.
- [ ] Não existem dependências externas bloqueando esta Issue.

---

### 🔗 Dependências

- **Bloqueada por:** nenhuma.
- **Desbloqueia:** nenhuma.

---

### 💻 Notas Técnicas

- A API já possui cobertura para o filtro de encerradas, `include_closed` e desempate determinístico; `status_priority` continuará disponível como ordenação explícita.
- O campo `Priority` da OS deve ser o critério primário da lista (`Urgente`, `Alta`, `Normal`, `Baixa`); antiguidade e `id` crescente desempatarão nessa ordem. O ranking por status permanece disponível apenas como ordenação explícita.
- A tela Angular atualmente envia `created_at_asc` quando `orderBy` não é informado; alinhar esse valor com o novo padrão `priority` da API.
- A regra de `ServiceOrder.set_priority` atualmente atribui prioridade sem validar o status; aplicar a regra de estados encerrados no domínio.
- Ampliar testes em `tests/integration/test_service_order_listing_api.py` e testes unitários do domínio; criar/ajustar teste do serviço Angular para os parâmetros da consulta.
