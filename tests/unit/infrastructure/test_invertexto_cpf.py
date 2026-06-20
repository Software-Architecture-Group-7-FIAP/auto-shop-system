import httpx
import pytest

from src.application.ports.cpf_validator import CpfValidationResult
from src.domain.exceptions import ValidationError
from src.infrastructure.external.invertexto_cpf import HttpInvertextoCpfValidator


def test_invertexto_cpf_validator_returns_formatted_cpf():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/validator"
        assert request.url.params["token"] == "test-token"
        assert request.url.params["value"] == "52998224725"
        return httpx.Response(
            200,
            json={"valid": True, "formatted": "529.982.247-25"},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    validator = HttpInvertextoCpfValidator(token="test-token", client=client)

    result = validator.validate("52998224725")

    assert result.valid is True
    assert result.formatted == "529.982.247-25"


def test_invertexto_cpf_validator_rejects_invalid_cpf():
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"valid": False, "formatted": "111.111.111-11"},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    validator = HttpInvertextoCpfValidator(token="test-token", client=client)

    with pytest.raises(ValidationError, match="CPF inválido"):
        validator.validate("11111111111")


def test_invertexto_cpf_validator_rejects_missing_token():
    validator = HttpInvertextoCpfValidator(token="")

    with pytest.raises(ValidationError, match="indisponível"):
        validator.validate("52998224725")


def test_invertexto_cpf_validator_rejects_unauthorized():
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(401)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    validator = HttpInvertextoCpfValidator(token="bad-token", client=client)

    with pytest.raises(ValidationError, match="indisponível"):
        validator.validate("52998224725")


def test_invertexto_cpf_validator_handles_server_error():
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    validator = HttpInvertextoCpfValidator(token="test-token", client=client)

    with pytest.raises(ValidationError, match="indisponível"):
        validator.validate("52998224725")


def test_invertexto_cpf_validator_handles_network_error():
    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection failed")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    validator = HttpInvertextoCpfValidator(token="test-token", client=client)

    with pytest.raises(ValidationError, match="indisponível"):
        validator.validate("52998224725")
