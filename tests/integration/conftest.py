from unittest.mock import patch

import pytest

from src.application.ports.cpf_validator import CpfValidationResult


@pytest.fixture(autouse=True)
def mock_cpf_validator():
    with patch(
        "src.infrastructure.external.invertexto_cpf.HttpInvertextoCpfValidator.validate"
    ) as mock_validate:
        mock_validate.return_value = CpfValidationResult(
            valid=True,
            formatted="529.982.247-25",
        )
        yield mock_validate
