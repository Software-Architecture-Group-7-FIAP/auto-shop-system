from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class CnpjValidationResult:
    valid: bool
    legal_name: str | None = None
    trade_name: str | None = None


class CnpjExternalValidator(Protocol):
    def validate(self, cnpj: str) -> CnpjValidationResult: ...
