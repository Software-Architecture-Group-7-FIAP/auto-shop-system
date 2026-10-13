# Proteção de branches (#91)

Política do repositório backend (`auto-shop-system`) para `main` e `develop`.
Nesta onda vale só este repositório. Frontend, infraestrutura e gateway recebem a mesma política quando deixarem de viver aqui (cenário 5 da #91, onda seguinte da #89).

## Regras

| Regra | `main` e `develop` |
|---|---|
| Push direto | Bloqueado. A entrada é pull request. |
| Review | 1 aprovação. |
| Checks obrigatórios | Os quatro jobs estáveis do CI, com a branch atualizada em relação à base. |
| Force push | Desligado. |
| Apagar a branch no merge | Ligado no repositório. |
| Bypass de admin | Só em emergência, com o motivo registrado num comentário da issue ou do PR. |

Checks obrigatórios agora, porque existem tanto no workflow atual (`security.yml`) quanto no CI da #89:

- `test-and-security`
- `manifests`
- `cluster-smoke`
- `frontend`

`terraform-plan` continua rodando no workflow atual, mas não entra na lista obrigatória: a #89 troca esse job por `terraform-k8s` e `terraform-aws`. Exigi-lo agora impediria o merge dessa PR.

Depois que a #89 entrar em `develop`, incluir também:

- `gateway`
- `terraform-k8s`
- `terraform-aws`

## Como aplicar

Na raiz do repositório, com `gh` autenticado e permissão de admin:

```bash
scripts/apply_branch_protection.sh
```

O script é idempotente. Para outro repositório do ecossistema, quando ele existir:

```bash
scripts/apply_branch_protection.sh ORG/repositorio
```
