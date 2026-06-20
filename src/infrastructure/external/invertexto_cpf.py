import logging

import httpx

from src.application.ports.cpf_validator import CpfValidationResult
from src.domain.exceptions import ValidationError

logger = logging.getLogger(__name__)

INVERTEXTO_VALIDATOR_URL = "https://api.invertexto.com/v1/validator"
INVERTEXTO_API_DOCS_URL = "https://api.invertexto.com/v1/validator"


class HttpInvertextoCpfValidator:
    def __init__(self, token: str, client: httpx.Client | None = None):
        self._token = token
        self._client = client

    def validate(self, cpf: str) -> CpfValidationResult:
        if not self._token:
            raise ValidationError("Serviço de validação de CPF indisponível")

        params = {"token": self._token, "value": cpf}
        logger.info(
            "Enviando informação para Invertexto API (%s) — consultando CPF %s",
            INVERTEXTO_API_DOCS_URL,
            cpf,
        )
        try:
            if self._client is not None:
                response = self._client.get(INVERTEXTO_VALIDATOR_URL, params=params)
            else:
                with httpx.Client(timeout=10.0) as client:
                    response = client.get(INVERTEXTO_VALIDATOR_URL, params=params)
        except httpx.RequestError as exc:
            raise ValidationError(
                "Serviço de validação de CPF indisponível"
            ) from exc

        if response.status_code == 401:
            raise ValidationError("Serviço de validação de CPF indisponível")
        if response.status_code >= 500:
            raise ValidationError("Serviço de validação de CPF indisponível")
        if response.status_code != 200:
            raise ValidationError("Cliente inválido")

        data = response.json()
        if not data.get("valid"):
            raise ValidationError("CPF inválido")

        logger.info("Invertexto API respondeu com sucesso para CPF %s", cpf)
        return CpfValidationResult(
            valid=True,
            formatted=data.get("formatted"),
        )
