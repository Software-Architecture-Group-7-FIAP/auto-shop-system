## Parent

- PRD #101 — [Correções da avaliação do professor, Fase 2](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/issues/101)

---

### 📖 User Story

**Como** mantenedor da API
**Quero** uma única política para converter erros de domínio em respostas HTTP
**Para que** rotas diferentes retornem contratos consistentes e o tratamento não seja repetido

---

### 🏛️ Contexto

- **Bounded Context:** API e tratamento transversal de erros
- **Agregado/Entidade Afetada:** Contrato HTTP de erros
- **PRD pai:** [Correções da avaliação da Fase 2](../../prd-revisao-professor-fase-2.md)

---

### ✅ Critérios de Aceite

- [ ] **Cenário 1: Erro de domínio retorna contrato padronizado**
  - **Dado que** um caso de uso lança um erro de domínio conhecido
  - **Quando** qualquer rota da API o propagar
  - **Então** a resposta deve usar o status HTTP correspondente e o envelope padronizado com `detail` e `code`

- [ ] **Cenário 2: Rotas não divergem no mesmo erro**
  - **Dado que** duas rotas propagam o mesmo tipo de erro de domínio
  - **Quando** as requisições forem comparadas
  - **Então** status e formato da resposta devem ser iguais

- [ ] **Cenário 3: Exceções inesperadas não são expostas como detalhes internos**
  - **Dado que** uma rota encontra uma exceção inesperada
  - **Quando** a API responder ao cliente
  - **Então** a resposta não deve revelar stack trace, SQL, segredo ou detalhe interno

- [ ] **Cenário 4: Regressão dos consumidores existentes**
  - **Dado que** os clientes atuais leem o campo `detail`
  - **Quando** o tratamento centralizado for aplicado
  - **Então** `detail` e os status HTTP existentes devem continuar compatíveis

- [ ] **Cenário 5: Conversões duplicadas são removidas**
  - **Dado que** o tratamento global da aplicação processa erros de domínio
  - **Quando** os routers forem revisados
  - **Então** não devem manter blocos repetidos que convertem `DomainError` para `HTTPException` sem necessidade

---

### 🛡️ Definition of Ready (DoR) - Checklist

- [ ] A User Story está clara e focada na manutenção e consistência da API.
- [ ] O envelope de erro compatível foi acordado (`detail` e `code`).
- [ ] Os status HTTP por código de domínio estão definidos.
- [ ] Os testes cobrem rotas com erros e uma exceção não esperada.
- [ ] Não existem dependências externas bloqueando esta Issue.

---

### 🔗 Dependências

- **Bloqueada por:** nenhuma.
- **Desbloqueia:** nenhuma.

---

### 💻 Notas Técnicas

- `src/main.py` já registra um handler global de `DomainError` que inclui `detail` e `code`.
- `src/api/dependencies.py` expõe `domain_error_handler`, que cria `HTTPException` contendo apenas `detail`; múltiplos routers repetem try/except para chamar esse helper.
- Preferir propagar erros de domínio ao handler global e centralizar o mapeamento de status, salvo exceções em que a rota tenha uma resposta contextual necessária.
- Atualizar testes HTTP que hoje esperam formatos divergentes; preservar compatibilidade de clientes do frontend.
