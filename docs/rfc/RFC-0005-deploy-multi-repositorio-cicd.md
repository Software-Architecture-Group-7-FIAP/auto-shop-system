# RFC-0005: Deploy e CI/CD multi-repositório

- **Status:** aceita como direção operacional
- **Data:** 2026-11-02
- **Decisões relacionadas:** [ADR-0071](../architecture/decisions/ADR-0071-infraestrutura-cloud-fase-3.md), [ADR-0074](../architecture/decisions/ADR-0074-estrategia-branches-e-ci.md)
- **Issues:** [#89](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/issues/89), [#90](https://github.com/Software-Architecture-Group-7-FIAP/auto-shop-system/issues/90)

## Resumo

Quatro repositórios com pipelines **independentes**, coordenados por contratos (imagens, secrets, ordem de provisionamento) e não por monorepo único de infraestrutura.

## Repositórios e papel

| Repositório | CI principal | Deploy / IaC |
| --- | --- | --- |
| `auto-shop-system` | `ci.yml` (app, gateway tf, k8s manifests, frontend) | `cd-staging.yml` / `cd-prod.yml` → GHCR + espelho ECR + `k8s/scripts/deploy.sh` |
| `k8s-infra` | Terraform cluster/VPC/ALB | apply em sessão autorizada |
| `database-infra` | Terraform RDS | apply em sessão autorizada |
| `lambda-auth` | testes + build/deploy Lambda | workflow próprio |

Templates compartilhados: [.github/ecosystem-templates/README.md](../../.github/ecosystem-templates/README.md).

## Fluxo típico (staging)

1. PR verde em cada repo → merge em `develop` (ou `main` onde aplicável).
2. Infra base (VPC, RDS, cluster) provisionada conforme ADR-0071 e issue #87.
3. Build da aplicação publica imagem imutável por digest; CD só roda com gate `DEPLOY_*_ENABLED` e OIDC.
4. Gateway e Lambda publicados nos repos respectivos; variáveis de integração documentadas em `infra/aws/` e ADR-0073.

## Consequências

- Versões de infra e app não são atômicas entre repos; runbooks devem registrar ordem e rollback por componente.
- Deploy ponta a ponta em staging aguarda #87; ver [.github/CD.md](../../.github/CD.md).

## Referências

- [Diagrama operacional](../architecture/fase-operacional.mmd)
- [CD.md](../../.github/CD.md)
