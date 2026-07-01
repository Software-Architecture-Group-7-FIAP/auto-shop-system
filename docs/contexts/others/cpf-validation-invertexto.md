# Validação externa de CPF — Invertexto API

Este documento descreve como o sistema valida **CPF** de clientes usando a [Invertexto API](https://api.invertexto.com/v1/validator), complementando a validação local (`validate_docbr`) e espelhando o fluxo já existente para **CNPJ** via [Brasil API](https://brasilapi.com.br/docs).

---

## Contexto (T02 — RF01 / RF05)

No cadastro de clientes, o sistema:

1. Normaliza e valida o documento localmente (dígitos verificadores via `validate_docbr`)
2. Verifica duplicidade no banco
3. **CPF (11 dígitos):** consulta a Invertexto API
4. **CNPJ (14 dígitos):** consulta a Brasil API
5. Persiste o cliente somente se todas as etapas passarem

---

## API Invertexto

### Requisição

```
GET https://api.invertexto.com/v1/validator?token={TOKEN}&value={cpf_digits}
```

| Parâmetro | Descrição |
|-----------|-----------|
| `token` | Token de autenticação obtido no cadastro Invertexto |
| `value` | CPF com **11 dígitos**, sem pontuação (ex.: `52998224725`) |

### Resposta (200 OK)

```json
{
  "valid": true,
  "formatted": "529.982.247-25"
}
```

Exemplo de CPF inválido:

```json
{
  "valid": false,
  "formatted": "111.111.111-11"
}
```

---

## Configuração

Adicione o token ao arquivo `.env`:

```env
INVERTEXTO_API_TOKEN=seu-token-aqui
```

Definido em [`src/config.py`](../src/config.py) como `invertexto_api_token`. Se o token estiver ausente, a validação externa de CPF retorna:

```
Serviço de validação de CPF indisponível
```

---

## Quando a validação é executada

| Operação | CPF externo |
|----------|-------------|
| `POST /api/v1/admin/customers` | Sim, se documento tiver 11 dígitos |
| `POST /api/v1/admin/customers/{id}/documents` | Sim, se novo documento for CPF |
| `GET /api/v1/admin/customers/validate-cpf/{cpf}` | Sim (pré-validação no frontend) |

---

## Endpoint administrativo

```
GET /api/v1/admin/customers/validate-cpf/{cpf}
Authorization: Bearer <jwt>
```

Resposta:

```json
{
  "valid": true,
  "formatted": "529.982.247-25"
}
```

Erros comuns:

| Situação | HTTP | Mensagem |
|----------|------|----------|
| CPF com formato inválido (local) | 422 | `CPF inválido` |
| Invertexto retorna `valid: false` | 422 | `CPF inválido` |
| Token ausente / API indisponível | 422 | `Serviço de validação de CPF indisponível` |
| Token rejeitado (401) | 422 | `Serviço de validação de CPF indisponível` |

---

## Implementação no código

| Camada | Arquivo |
|--------|---------|
| Porta (contrato) | [`src/application/ports/cpf_validator.py`](../src/application/ports/cpf_validator.py) |
| Adaptador HTTP | [`src/infrastructure/external/invertexto_cpf.py`](../src/infrastructure/external/invertexto_cpf.py) |
| Caso de uso | [`src/application/services/customer_service.py`](../src/application/services/customer_service.py) |
| Composição DI | [`src/api/composition/customers.py`](../src/api/composition/customers.py) |
| Rota REST | [`src/api/routers/customers.py`](../src/api/routers/customers.py) |

---

## Logs no terminal

Ao validar um CPF, o servidor registra:

```
INFO: src.infrastructure.external.invertexto_cpf - Enviando informação para Invertexto API (https://api.invertexto.com/v1/validator) — consultando CPF 52998224725
INFO: src.infrastructure.external.invertexto_cpf - Invertexto API respondeu com sucesso para CPF 52998224725
```

Visível no terminal do `uvicorn` quando `INVERTEXTO_API_TOKEN` está configurado.

---

## Comparação CPF vs CNPJ

| Aspecto | CPF | CNPJ |
|---------|-----|------|
| Provedor | Invertexto | Brasil API |
| URL base | `https://api.invertexto.com/v1/validator` | `https://brasilapi.com.br/api/cnpj/v1/{cnpj}` |
| Autenticação | Query param `token` | Nenhuma |
| Dados extras | `formatted` | `razao_social`, `nome_fantasia` |
| Endpoint pré-validação | `GET .../validate-cpf/{cpf}` | `GET .../validate-cnpj/{cnpj}` |
| Validação local prévia | `validate_docbr` | `validate_docbr` |

---

## Frontend

O painel Angular exibe **Validar CPF** quando o campo de documento contém 11 dígitos, e **Validar CNPJ** para 14 dígitos. O botão chama o endpoint correspondente antes do salvamento.

Arquivos: `frontend/src/app/service/customer.service.ts`, formulários em `new-customer` e `customer-detail`.
