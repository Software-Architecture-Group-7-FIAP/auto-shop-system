## Parent

- PRD #101 — [Correções da avaliação do professor, Fase 2](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/issues/101)

---

### 📖 User Story

**Como** responsável pela oficina
**Quero** testes para os caminhos de aprovação e recusa de orçamento
**Para que** regressões de estado ou de efeitos sobre a ordem de serviço sejam detectadas antes da entrega

---

### 🏛️ Contexto

- **Bounded Context:** Orçamentos e Ordem de Serviço
- **Agregado/Entidade Afetada:** Orçamento, Ordem de Serviço e reservas
- **PRD pai:** [Correções da avaliação da Fase 2](../../prd-revisao-professor-fase-2.md)

---

### ✅ Critérios de Aceite

- [ ] **Cenário 1: Aprovação válida cria os efeitos esperados uma única vez**
  - **Dado que** o orçamento está enviado, possui token válido e pode ser aprovado
  - **Quando** o cliente aprovar pela API pública
  - **Então** a resposta, o estado persistido do orçamento e a criação da OS devem corresponder ao contrato existente
  - **E** uma repetição não deve criar uma OS duplicada

- [ ] **Cenário 2: Recusa válida atualiza os agregados relacionados**
  - **Dado que** o orçamento está enviado e possui token válido
  - **Quando** o cliente recusar pela API pública
  - **Então** o orçamento deve ficar recusado e os efeitos atuais sobre OS e reservas devem ser verificados pela resposta e pelo estado persistido

- [ ] **Cenário 3: Token expirado, desconhecido ou orçamento em estado incompatível**
  - **Dado que** a decisão não pode ser aplicada
  - **Quando** o cliente tentar aprovar ou recusar
  - **Então** a API deve rejeitar a operação sem efeitos parciais

- [ ] **Cenário 4: Decisão repetida ou oposta**
  - **Dado que** o token já foi consumido por uma decisão
  - **Quando** houver repetição da mesma decisão ou tentativa da decisão oposta
  - **Então** o resultado deve seguir a política idempotente atual e não duplicar OS, histórico ou reservas

- [ ] **Cenário 5: Matriz de transições do domínio**
  - **Dado que** cada status de orçamento permitido ou proibido é usado como estado de origem
  - **Quando** aprovação, recusa ou reenvio for executado
  - **Então** cada transição válida deve ser aceita e cada transição inválida deve retornar erro de domínio

---

### 🛡️ Definition of Ready (DoR) - Checklist

- [ ] A User Story está clara e focada em valor para a oficina.
- [ ] O Bounded Context e os agregados afetados foram identificados.
- [ ] Os critérios cobrem aprovação, recusa, repetição, estados inválidos e efeitos persistidos.
- [ ] O contrato público atual e a política idempotente existente foram confirmados.
- [ ] Não existem dependências externas bloqueando os testes.

---

### 🔗 Dependências

- **Bloqueada por:** nenhuma.
- **Desbloqueia:** nenhuma.

---

### 💻 Notas Técnicas

- Manter a implementação de regras inalterada enquanto os testes ainda não evidenciarem um defeito funcional.
- Complementar os testes em `tests/unit/budget_approval` e os testes HTTP em `tests/integration` para a rota pública de decisões.
- Usar dados sintéticos e verificar persistência após a requisição, incluindo OS, histórico e reservas quando aplicável.
- Os fluxos unitários já existentes de aprovação e recusa não substituem a validação integrada da recusa pela API.
