# ADR-0075: Escala de Pods com HPA e sem Cluster Autoscaler

- **Status:** aceito para o desenho; calibração em homologação pendente
- **Data:** 2026-10-27
- **Issues:** [auto-shop-system #87](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/issues/87), [k8s-infra #6](https://github.com/Software-Architecture-Group-7-FIAP/k8s-infra/issues/6)

## Contexto

A demonstração da Fase 3 precisa mostrar a aplicação aumentando e reduzindo o número de Pods sob carga. O escopo atualizado da issue #87 exige evidência de HPA e exclui Cluster Autoscaler. O staging é efêmero e usa capacidade de nós definida antes da sessão.

## Decisão

Usar Kubernetes Horizontal Pod Autoscaler para ajustar as réplicas da aplicação conforme os recursos declarados nos manifests. Manter fixa a capacidade do node group durante a sessão e não instalar Cluster Autoscaler.

O HPA escala Pods dentro da capacidade disponível; ele não aumenta a capacidade dos nós. A arquitetura não promete acomodar carga que exceda essa capacidade.

## Alternativas consideradas

- **HPA e Cluster Autoscaler:** adicionaria outra camada de escala e mais componentes a operar. Não é necessária para o critério de demonstração vigente.
- **Réplicas fixas:** não demonstraria a reação horizontal de Pods exigida pela entrega.
- **HPA sem limites de capacidade:** poderia deixar Pods pendentes quando os nós não comportarem novas réplicas.

## Consequências e validação

- Requests e limites dos Pods, métricas disponíveis e limites mínimo/máximo precisam ser compatíveis com os nós do staging.
- O teste de carga precisa registrar réplicas antes, durante e depois da carga.
- A calibração em carga representativa continua pendente em k8s-infra#6; a evidência integrada continua no gate auto-shop-system#87.
- Escalar nós exige novo ADR, revisão de custo e atualização do plano de teardown.

## Referências

- [Horizontal Pod Autoscaling, Kubernetes](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/)
- [Amazon EKS Best Practices Guide](https://docs.aws.amazon.com/eks/latest/best-practices/introduction.html)
