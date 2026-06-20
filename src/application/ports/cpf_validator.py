from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class CpfValidationResult:
    valid: bool
    formatted: str | None = None


class CpfExternalValidator(Protocol):
    def validate(self, cpf: str) -> CpfValidationResult: ...
