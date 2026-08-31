import logging

import httpx

from src.application.ports.cnpj_validator import CnpjValidationResult
from src.domain.exceptions import ValidationError

logger = logging.getLogger(__name__)

BRASIL_API_CNPJ_URL = "https://brasilapi.com.br/api/cnpj/v1/{cnpj}"
CNPJ_NOT_FOUND_MESSAGE = (
    "CNPJ não encontrado. Verifique se os números estão corretos ou se o documento "
    "foi emitido recentemente e ainda não reflete nas bases governamentais."
)


class HttpBrasilApiCnpjValidator:
    def __init__(self, client: httpx.Client | None = None):
        self._client = client

    def validate(self, cnpj: str) -> CnpjValidationResult:
        url = BRASIL_API_CNPJ_URL.format(cnpj=cnpj)
        logger.info("Enviando solicitação de validação para Brasil API")
        try:
            if self._client is not None:
                response = self._client.get(url)
            else:
                with httpx.Client(timeout=10.0) as client:
                    response = client.get(url)
        except httpx.RequestError as exc:
            raise ValidationError(
                "Serviço de validação de CNPJ indisponível"
            ) from exc

        if response.status_code == 404:
            raise ValidationError(CNPJ_NOT_FOUND_MESSAGE)
        if response.status_code >= 500:
            raise ValidationError("Serviço de validação de CNPJ indisponível")
        if response.status_code != 200:
            raise ValidationError("Cliente inválido")

        data = response.json()
        logger.info("Brasil API respondeu com sucesso")
        return CnpjValidationResult(
            valid=True,
            legal_name=data.get("razao_social"),
            trade_name=data.get("nome_fantasia"),
        )
