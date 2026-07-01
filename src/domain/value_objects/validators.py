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
            raise ValidationError("Documento inválido")
        return cleaned


class PlateValidator:
    LEGACY_PATTERN = re.compile(r"^[A-Z]{3}[0-9]{4}$")
    MERCOSUL_PATTERN = re.compile(r"^[A-Z]{3}[0-9][A-Z0-9][0-9]{2}$")

    @classmethod
    def validate(cls, plate: str) -> str:
        normalized = plate.upper().replace("-", "").replace(" ", "")
        if cls.LEGACY_PATTERN.match(normalized) or cls.MERCOSUL_PATTERN.match(normalized):
            return normalized
        raise ValidationError("Veículo inválido")


class StateValidator:
    VALID_STATES = frozenset(
        {
            "AC",
            "AL",
            "AP",
            "AM",
            "BA",
            "CE",
            "DF",
            "ES",
            "GO",
            "MA",
            "MT",
            "MS",
            "MG",
            "PA",
            "PB",
            "PR",
            "PE",
            "PI",
            "RJ",
            "RN",
            "RS",
            "RO",
            "RR",
            "SC",
            "SP",
            "SE",
            "TO",
        }
    )

    @classmethod
    def validate(cls, state: str) -> str:
        normalized = state.strip().upper()
        if normalized not in cls.VALID_STATES:
            raise ValidationError("UF inválida")
        return normalized
