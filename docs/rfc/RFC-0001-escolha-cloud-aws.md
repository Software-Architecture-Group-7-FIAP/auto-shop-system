# RFC-0001: Escolha do provedor de nuvem da Fase 3

- **Status:** aceita como direção arquitetural
- **Data:** 2026-10-27
- **Decisão relacionada:** [ADR-0071](../architecture/decisions/ADR-0071-infraestrutura-cloud-fase-3.md)

## Resumo

Adotar AWS como provedor cloud da Fase 3. A escolha atende ao requisito de demonstrar autenticação e notificações serverless, aplicação em Kubernetes, banco relacional gerenciado e entrada pública controlada.

Este RFC registra a escolha do provedor. O desenho de recursos e contratos entre repositórios permanece no ADR-0071. A decisão não comprova que os recursos foram implantados.

## Contexto e restrições

A entrega integra quatro repositórios: aplicação, autenticação serverless, infraestrutura Kubernetes e banco. O projeto precisa demonstrar os fluxos de cliente e administrador, persistência relacional, evento operacional e deploy por ambiente.

O código e os planos da Fase 3 já usam serviços AWS, Terraform, IAM e GitHub Actions com OIDC. Trocar o provedor exigiria substituir integrações preparadas e revalidar contratos entre repositórios.

## Alternativas

| Alternativa | Vantagens | Custos e riscos para esta entrega |
| --- | --- | --- |
| AWS | Integra Lambda, API Gateway, KMS, EventBridge, SNS, EKS, RDS, S3 e CloudFront; segue os artefatos existentes. | Exige configuração cuidadosa de IAM, rede, identidade entre repositórios e ciclo de criação/destruição. |
| Azure ou Google Cloud | Oferecem serviços gerenciados para funções, Kubernetes, banco e observabilidade. | Exigiriam portar módulos Terraform e integrações já preparados para AWS, aumentando o trabalho sem atender a requisito adicional. |
| Execução somente local | Baixo custo e ciclo de desenvolvimento simples. | Não demonstra os serviços serverless e gerenciados solicitados para a Fase 3. |

## Decisão

Usar AWS para o ambiente cloud efêmero da Fase 3. O conjunto de serviços e a topologia são definidos no ADR-0071 e nas issues dos repositórios. O desenvolvimento local continua disponível para ciclos de código e teste.

## Consequências

- IAM, KMS, rede privada e exposição pública permanecem sob infraestrutura como código e revisão por PR.
- A infraestrutura demonstrável é criada apenas em sessões autorizadas e destruída conforme ADR-0071 e issue #87.
- Custos, limites de conta e elegibilidade de planos devem ser conferidos antes de cada sessão. Este RFC não fixa uma estimativa de custo.
- A escolha do provedor não comprova que o ambiente integrado esteja disponível; a issue #87 mantém esse gate.

## Referências

- [Amazon EKS](https://docs.aws.amazon.com/eks/latest/userguide/what-is-eks.html)
- [Amazon RDS for PostgreSQL](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_PostgreSQL.html)
- [AWS Lambda](https://docs.aws.amazon.com/lambda/latest/dg/welcome.html)
- [Amazon API Gateway](https://docs.aws.amazon.com/apigateway/latest/developerguide/welcome.html)
- [Issue #87: ambiente de staging](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/issues/87)
