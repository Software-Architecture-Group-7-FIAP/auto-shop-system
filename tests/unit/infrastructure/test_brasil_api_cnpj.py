import httpx
import pytest

from src.domain.exceptions import ValidationError
from src.infrastructure.external.brasil_api_cnpj import HttpBrasilApiCnpjValidator


def test_brasil_api_cnpj_validator_returns_company_data():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/04252011000110")
        return httpx.Response(
            200,
            json={"razao_social": "Empresa LTDA", "nome_fantasia": "Empresa"},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    validator = HttpBrasilApiCnpjValidator(client=client)

    result = validator.validate("04252011000110")

    assert result.valid is True
    assert result.legal_name == "Empresa LTDA"
    assert result.trade_name == "Empresa"


def test_brasil_api_cnpj_validator_rejects_not_found():
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    validator = HttpBrasilApiCnpjValidator(client=client)

    with pytest.raises(ValidationError, match="Cliente inválido"):
        validator.validate("04252011000110")


def test_brasil_api_cnpj_validator_handles_server_error():
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    validator = HttpBrasilApiCnpjValidator(client=client)

    with pytest.raises(ValidationError, match="indisponível"):
        validator.validate("04252011000110")


def test_brasil_api_cnpj_validator_handles_network_error():
    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection failed")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    validator = HttpBrasilApiCnpjValidator(client=client)

    with pytest.raises(ValidationError, match="indisponível"):
        validator.validate("04252011000110")
