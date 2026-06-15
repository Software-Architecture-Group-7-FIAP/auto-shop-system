import re

from validate_docbr import CNPJ, CPF

from src.domain.exceptions import ValidationError


class DocumentValidator:
    @staticmethod
    def validate(document: str) -> str:
        cleaned = re.sub(r"\D", "", document)
        if len(cleaned) == 11:
            if not CPF().validate(cleaned):
                raise ValidationError("CPF inválido")
        elif len(cleaned) == 14:
            if not CNPJ().validate(cleaned):
                raise ValidationError("CNPJ inválido")
        else:
            raise ValidationError("Documento deve ser CPF (11 dígitos) ou CNPJ (14 dígitos)")
        return cleaned


class PlateValidator:
    LEGACY_PATTERN = re.compile(r"^[A-Z]{3}[0-9]{4}$")
    MERCOSUL_PATTERN = re.compile(r"^[A-Z]{3}[0-9][A-Z0-9][0-9]{2}$")

    @classmethod
    def validate(cls, plate: str) -> str:
        normalized = plate.upper().replace("-", "").replace(" ", "")
        if cls.LEGACY_PATTERN.match(normalized) or cls.MERCOSUL_PATTERN.match(normalized):
            return normalized
        raise ValidationError("Placa inválida (formato antigo ou Mercosul)")
