import pytest

from src.domain.exceptions import ValidationError
from src.domain.value_objects.validators import DocumentValidator, PlateValidator


class TestDocumentValidator:
    def test_valid_cpf(self):
        assert DocumentValidator.validate("529.982.247-25") == "52998224725"

    def test_valid_cnpj(self):
        assert DocumentValidator.validate("04.252.011/0001-10") == "04252011000110"

    def test_invalid_document(self):
        with pytest.raises(ValidationError, match="Documento inválido"):
            DocumentValidator.validate("123")


class TestPlateValidator:
    def test_legacy_plate(self):
        assert PlateValidator.validate("ABC1234") == "ABC1234"

    def test_mercosul_plate(self):
        assert PlateValidator.validate("ABC1D23") == "ABC1D23"

    def test_invalid_plate(self):
        with pytest.raises(ValidationError):
            PlateValidator.validate("INVALID")
