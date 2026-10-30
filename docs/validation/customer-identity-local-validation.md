# Evidência de validação local — identidade do cliente e eventos de OS

- **Data:** 2026-10-27
- **Branch:** `F3P1-02-customer-access-events`
- **Código validado:** `e740df3` (`fix: prevent caching customer service order responses`), com dependências atualizadas localmente no `pyproject.toml` e `poetry.lock`
- **Ambiente:** Windows, Python 3.14.4, pytest 9.1.1, Bandit 1.9.4

Esta evidência cobre somente o checkout local indicado acima. Os testes usam fixtures e adaptadores falsos; nenhum serviço AWS, ambiente de homologação ou dado real de cliente foi acessado.

## Resultados

| Verificação | Resultado |
| --- | --- |
| Testes direcionados de status do cliente, JWT, autorização da OS, evento de falha, regressão administrativa e geração de PDF | **101 passaram**, 239 avisos, em 45,29 s |
| Bandit `-r src -ll` | **0 achados médios ou altos** em 10.535 linhas; o relatório resumido indicou 4 achados de baixa severidade, abaixo do limiar `-ll` |
| `poetry check --lock` | Passou, com avisos de depreciação de metadados Poetry já existentes |
| `poetry run pip-audit --skip-editable` | **Nenhuma vulnerabilidade conhecida** nas dependências instaladas; o próprio projeto foi ignorado por estar instalado em modo editável |
| `git diff --check` | Passou; Git apenas avisou que normalizará LF para CRLF nos ADRs 0064 e 0066 já modificados localmente |

Dependências atualizadas neste checkout: `certifi 2026.10.23`, `dnspython 2.9.0`, `filelock 4.2.4`, `msgpack 1.2.3` e `pillow 13.0.0`. `msgpack` também foi atualizado no requisito direto de `pyproject.toml`; as demais atualizações estão registradas em `poetry.lock`.

Arquivos de teste executados:

- `tests/unit/test_migration_customer_access_status.py`
- `tests/unit/customer/`
- `tests/unit/auth/test_jwt.py`
- `tests/unit/auth/test_jwt_algorithm.py`
- `tests/integration/test_customer_status_api.py`
- `tests/integration/test_customer_jwt_auth.py`
- `tests/integration/test_customer_service_orders.py`
- `tests/unit/test_eventbridge_publisher.py`
- `tests/unit/execution/test_execution_service.py`
- `tests/integration/test_auth_gateway.py`
- `tests/unit/infrastructure/test_pdf_generator.py`
- `tests/infrastructure/adapters/test_reportlab_pdf_generator.py`

Os avisos do pytest foram principalmente deprecations do SQLAlchemy e do `TestClient`, avisos de tamanho de chaves HMAC usadas em fixtures de teste e um aviso do cache local do pytest no Windows. Eles não causaram falhas.

## Verificações não executadas

- Homologação AWS: não executada. O roteiro de [homologação da autenticação](lambda-homologation.md) continua preparado e pendente de ambiente integrado.
- Integração real com API Gateway, Lambda, banco gerenciado ou EventBridge: não executada.

Para concluir a validação integrada, ainda são necessárias as URLs e os commits implantados, banco e cadastros sintéticos, configuração de JWT/JWKS e o procedimento aprovado para provocar falha operacional. Nenhum token, CPF, segredo, identificador real ou payload pessoal foi registrado nesta evidência.
