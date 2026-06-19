from src.domain.value_objects.validators import DocumentValidator


class SupplierDocument(str):
    def __new__(cls, raw: str) -> "SupplierDocument":
        normalized = DocumentValidator.validate(raw)
        return str.__new__(cls, normalized)

    @classmethod
    def create(cls, raw: str) -> "SupplierDocument":
        return cls(raw)
