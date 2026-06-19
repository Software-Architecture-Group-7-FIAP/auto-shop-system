from src.domain.value_objects.validators import DocumentValidator


class CustomerDocument(str):
    def __new__(cls, raw: str) -> "CustomerDocument":
        normalized = DocumentValidator.validate(raw)
        return str.__new__(cls, normalized)

    @classmethod
    def create(cls, raw: str) -> "CustomerDocument":
        return cls(raw)
