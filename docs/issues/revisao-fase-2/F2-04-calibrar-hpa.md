## PRD relacionado

- PRD #101 — [Correções da avaliação do professor, Fase 2](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/issues/101)

---

### 📖 User Story

**Como** operador da aplicação
**Quero** metas do HPA baseadas em medições e consistentes entre Kubernetes e Terraform
**Para que** a aplicação escale de forma previsível quando a carga mudar

---

### 🏛️ Contexto

- **Bounded Context:** Infraestrutura e escalabilidade da aplicação
- **Agregado/Entidade Afetada:** Deployment e Horizontal Pod Autoscaler
- **PRD pai:** [Correções da avaliação da Fase 2](../../prd-revisao-professor-fase-2.md)

---

### ✅ Critérios de Aceite

- [ ] **Cenário 1: Metas são justificadas por um perfil de carga**
  - **Dado que** a aplicação roda com carga representativa de homologação
  - **Quando** CPU, memória, latência e taxa de erros forem medidas
  - **Então** requests, limits, metas, mínimo, máximo e comportamento de escala devem ser calibrados e documentados com os resultados

- [ ] **Cenário 2: Kubernetes e Terraform expressam a mesma política**
  - **Dado que** os manifests e a infraestrutura declaram o HPA
  - **Quando** ambos forem renderizados/planejados
  - **Então** métricas, limites e comportamento de escala devem ser equivalentes

- [ ] **Cenário 3: HPA recebe métricas utilizáveis**
  - **Dado que** o cluster de validação está pronto
  - **Quando** a aplicação estiver sob carga controlada
  - **Então** CPU/memória devem estar disponíveis pela Metrics API e o HPA não deve permanecer em `unknown` por falta do provedor

- [ ] **Cenário 4: HPA é a fonte de escala das réplicas**
  - **Dado que** o HPA está ativo
  - **Quando** manifests ou Terraform forem reaplicados
  - **Então** uma contagem declarativa fixa não deve sobrescrever a escala calculada pelo autoscaler

- [ ] **Cenário 5: A política escala para cima e para baixo**
  - **Dado que** a carga controlada ultrapassa e depois fica abaixo das metas por tempo suficiente
  - **Quando** o HPA reconciliar as métricas
  - **Então** a quantidade de réplicas deve subir e descer respeitando limites e janelas de estabilização documentados

---

### 🛡️ Definition of Ready (DoR) - Checklist

- [ ] A User Story está clara e focada na operação da aplicação.
- [ ] Um perfil de carga e limites de latência/erro para homologação foram definidos.
- [ ] O cluster de teste disponibiliza Metrics Server/Metrics API.
- [ ] A configuração declarada em manifests e Terraform foi mapeada.
- [ ] Requests/limits foram definidos com o time da aplicação.
- [ ] A dependência de provisionamento de nodes (#74) foi concluída.

---

### 🔗 Dependências

- **Bloqueada por:** #74 e disponibilidade de perfil de carga/metas de serviço para homologação.
- **Desbloqueia:** validação reproduzível de escalabilidade da aplicação.

---

### 💻 Notas Técnicas

- Os manifests e `infra/k8s.tf` atualmente usam CPU 70% e memória 80%; os valores não vêm acompanhados de medição de carga documentada.
- `k8s/base/app/deployment.yaml`, o overlay local e Terraform declaram contagens de réplicas enquanto o HPA controla o mesmo campo. Alinhar a propriedade para evitar drift.
- A documentação atual admite métricas `unknown` sem Metrics Server; a validação não deve tratar essa condição como sucesso.
- Manter a política Kubernetes e Terraform coerente; adicionar teste/validação no pipeline de cluster já existente.
- Não escolher percentuais novos por estimativa. A issue só pode ser concluída com medições e metas aprovadas/documentadas.
- A validação funcional no Kind pode reduzir temporariamente o alvo de CPU para provar que o controlador escala; esse teste não calibra os alvos de produção.
