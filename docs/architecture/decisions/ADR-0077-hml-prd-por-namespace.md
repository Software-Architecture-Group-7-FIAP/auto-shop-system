# ADR-0077: Ambientes HML e PRD por namespace

- **Status:** aceito para o desenho da entrega; execução permanece sujeita ao ADR-0064
- **Data:** 2026-10-27
- **Issue:** [auto-shop-system #87](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/issues/87)
- **Decisão relacionada:** [ADR-0071](ADR-0071-infraestrutura-cloud-fase-3.md)

## Contexto

A entrega precisa demonstrar fluxos de homologação e produção. Dois clusters e duas instâncias de banco aumentariam custo e trabalho de operação de uma sessão acadêmica efêmera.

## Decisão

Manter uma infraestrutura cloud de staging efêmera e separar os ambientes lógicos da aplicação:

- Namespaces auto-shop-hml e auto-shop-prd no mesmo cluster EKS.
- Databases autoshop_hml e autoshop_prd na mesma instância RDS.
- Stages hml e prd no API Gateway.
- Target groups e configurações de aplicação separados por ambiente.
- Entradas, credenciais e políticas de acesso distintas por ambiente, conforme os contratos do ADR-0071.

prd é o ambiente lógico de demonstração da Fase 3. Não representa uma conta, cluster ou banco de produção independente, nem implica disponibilidade ou isolamento de produção real.

## Alternativas consideradas

- **Dois clusters e bancos independentes:** maior isolamento, custo e tempo de provisionamento, sem requisito de alta disponibilidade para esta entrega.
- **Um namespace e database compartilhados:** reduz custo, mas impede demonstrar separação de configuração e dados entre HML e PRD.

## Consequências e validação

- Manifests devem ser aplicados no namespace correto; o pipeline seleciona stage, database e target group consistentes.
- Os workflows session-up e session-down precisam criar e destruir infraestrutura na ordem definida pela issue #118.
- A issue #87 exige verificar persistência dos fluxos nos dois databases e destruição sem recursos órfãos.
- A execução de qualquer sessão AWS permanece sujeita às autorizações registradas no ADR-0064.

## Referências

- [ADR-0071: infraestrutura cloud da Fase 3](ADR-0071-infraestrutura-cloud-fase-3.md)
- [Issue #118: ciclo de vida da sessão AWS](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/issues/118)
