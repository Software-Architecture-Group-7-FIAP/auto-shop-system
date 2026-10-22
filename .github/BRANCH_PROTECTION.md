# Proteção de branches (#91)

Política do repositório backend (`auto-shop-system`) para `main` e `develop`.
Nesta onda vale só este repositório. Frontend, infraestrutura e gateway recebem a mesma política quando deixarem de viver aqui (cenário 5 da #91, onda seguinte da #89).

## Regras

| Regra | `main` e `develop` |
|---|---|
| Push direto | Bloqueado. A entrada é pull request. |
| Review | 1 aprovação; **nova aprovação após push** na PR (`require_last_push_approval`). |
| Checks obrigatórios | Jobs do workflow [`ci.yml`](./workflows/ci.yml), com a branch atualizada em relação à base (`strict`). |
| Force push | Desligado. |
| Apagar a branch no merge | Ligado no repositório. |
| Bypass de admin | Só em emergência, com o motivo registrado num comentário da issue ou do PR. |

Checks obrigatórios no backend (workflow `ci.yml`, issue #89):

- `test-and-security`
- `gateway`
- `manifests`
- `terraform-k8s`
- `terraform-aws`
- `cluster-smoke`
- `frontend`

O job `metadata` só gera outputs para outros jobs e **não** entra na proteção. Workflows de CD (`cd-staging.yml`, `cd-prod.yml`) rodam em push pós-merge, não em pull request. O antigo `terraform-plan` do `security.yml` foi substituído por `terraform-k8s` e `terraform-aws`.

## Como aplicar

Na raiz do repositório, com `gh` autenticado e permissão de admin:

```bash
scripts/apply_branch_protection.sh
```

Backend (padrão):

```bash
scripts/apply_branch_protection.sh Software-Architecture-Group-7-FIAP/auto-shop-system
```

Outro repositório — informe os **nomes exatos dos jobs** do `ci.yml` daquele repo, separados por vírgula (cada ecossistema tem checks diferentes):

```bash
scripts/apply_branch_protection.sh ORG/lambda-auth 'test-and-security,terraform'
```

O script é idempotente. Depois que esta PR entrar em `develop`, rode-o de novo no remoto se os required checks ainda forem só os quatro jobs legados do `security.yml`.
