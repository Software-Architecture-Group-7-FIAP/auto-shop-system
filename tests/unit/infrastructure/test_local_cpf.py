import pytest

from src.application.ports.cpf_validator import CpfValidationResult
from src.domain.exceptions import ValidationError
from src.infrastructure.external.local_cpf import LocalCpfValidator


def test_local_cpf_validator_accepts_valid_cpf():
    result = LocalCpfValidator().validate("52998224725")

    assert result == CpfValidationResult(valid=True, formatted="529.982.247-25")


def test_local_cpf_validator_rejects_invalid_cpf():
    with pytest.raises(ValidationError, match="CPF inválido"):
        LocalCpfValidator().validate("11111111111")
