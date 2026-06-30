from validate_docbr import CPF

from src.application.ports.cpf_validator import CpfValidationResult
from src.domain.exceptions import ValidationError


class LocalCpfValidator:
    """Validates CPF locally (validate_docbr) without calling Invertexto API."""

    def validate(self, cpf: str) -> CpfValidationResult:
        if not CPF().validate(cpf):
            raise ValidationError("CPF inválido")
        return CpfValidationResult(valid=True, formatted=CPF().mask(cpf))
