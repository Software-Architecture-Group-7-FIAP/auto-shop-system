# Oficina Mecânica — Frontend Angular

Painel administrativo em **Angular 15** com layout master-detail (lista + formulário), integrado à API FastAPI em `/api/v1`.

## Pré-requisitos

- Node.js 18+ e npm
- API rodando em `http://localhost:8000` (veja README na raiz do projeto)

## Instalação e execução

```bash
cd frontend
npm install
npm start
```

Abra [http://localhost:4200](http://localhost:4200).

Login: `admin` / senha definida em `DEV_ADMIN_PASSWORD` ao rodar o seed do backend.

Em banco novo, execute na raiz do projeto antes de entrar no painel:

```bash
DEV_ADMIN_PASSWORD=<senha-forte> poetry run python -m src.scripts.seed_dev_admin
```

O proxy em `proxy.conf.json` encaminha `/api/*` para `http://localhost:8000`.

## Rotas

| Rota | Entidade |
|------|----------|
| `/customers` | Clientes |
| `/vehicles` | Veículos |
| `/catalog-services` | Catálogo de serviços |
| `/products` | Produtos / peças |
| `/suppliers` | Fornecedores |
| `/budgets` | Orçamentos |
| `/service-orders` | Ordens de serviço |

## Painel legado (vanilla JS)

O painel T02 original continua em `legacy-panel/` e é servido pela API em `/app/`.

## Build de produção

```bash
npm run build
```

Saída em `dist/oficina-frontend/`. Sirva os arquivos estáticos atrás de um reverse proxy apontando `/api` para o backend.
