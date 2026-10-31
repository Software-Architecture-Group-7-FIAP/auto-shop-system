# RFC-0003: Autenticação de cliente por CPF e JWT

- **Status:** aceita para a entrega acadêmica; implantação e homologação pendentes
- **Data:** 2026-10-27
- **Decisão relacionada:** [ADR-0064](../architecture/decisions/ADR-0064-autenticacao-cliente-cpf-jwt.md)

## Resumo

Usar uma Lambda dedicada para validar CPF, consultar o status do cliente e emitir JWT de curta duração assinado com RS256 pelo AWS KMS. Publicar chaves públicas em JWKS para que a API FastAPI valide tokens sem compartilhar a chave privada.

## Contexto

A autenticação administrativa e a autenticação de clientes têm papéis e contratos diferentes. A Function consulta a tabela compartilhada de clientes com identidade de leitura; a aplicação principal autoriza consultas às ordens de serviço.

A Fase 3 mantém os repositórios da aplicação e da Lambda separados e requer que os consumidores validem a assinatura pública do token.

## Alternativas

| Alternativa | Avaliação |
| --- | --- |
| HS256 com segredo compartilhado entre Lambda e API | Cada consumidor que verifica o token também teria acesso ao segredo de assinatura. O acoplamento dificulta limitar emissão e rotação. |
| Reutilizar a autenticação administrativa | Misturaria identidades, permissões e ciclos de vida diferentes. |
| RS256 com KMS e JWKS | A Lambda mantém a operação de assinatura; a API recebe apenas a chave pública e valida tokens pelo kid. |

## Decisão

- O endpoint serverless recebe CPF e valida formato e dígitos antes da consulta ao banco.
- Somente cliente ativo recebe Bearer JWT. A validade configurada não excede 900 segundos.
- RS256 é assinado por chave assimétrica do AWS KMS. O endpoint JWKS publica chaves públicas e seus kid.
- O consumidor valida algoritmo, kid, issuer, audience, expiração e escopo.
- Claims não contêm CPF ou outros dados pessoais. CPF não deve aparecer em logs, traces ou mensagens de erro.
- Cliente inexistente e inativo recebem a mesma resposta pública.
- A sessão administrativa permanece independente.

## Limitações e consequências

CPF sozinho não demonstra posse da identidade. Esta decisão atende ao escopo acadêmico atual e não define autenticação adequada para uso financeiro ou produção. Antes de uso real, deve-se avaliar prova adicional de posse, como OTP, e uma política de recuperação.

A implementação em código não comprova integração entre Lambda, API Gateway, KMS, banco e aplicação. A issue #68 acompanha os cenários em homologação. Nenhuma chave privada ou segredo deve ser incluído na documentação.

## Referências

- [ADR-0064: autenticação de cliente por CPF com JWT](../architecture/decisions/ADR-0064-autenticacao-cliente-cpf-jwt.md)
- [AWS KMS asymmetric keys](https://docs.aws.amazon.com/kms/latest/developerguide/symmetric-asymmetric.html)
- [JSON Web Key Sets, RFC 7517](https://www.rfc-editor.org/rfc/rfc7517)
- [JWT, RFC 7519](https://www.rfc-editor.org/rfc/rfc7519)
